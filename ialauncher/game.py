import os, sys
import shutil
import subprocess
from zipfile import ZipFile
from urllib import request
from urllib.parse import unquote
from configparser import RawConfigParser
from threading import Thread

from .dosbox import get_dosbox_path

DOSBOX = get_dosbox_path()

class Game:
    def __init__(self, path):
        self.path = path
        self.gamedir = os.path.join(self.path, 'dosbox_drive_c')
        self.identifier = os.path.basename(path)
        self.configured = False
        self.download_thread = None

    def configure(self):
        self.config = c = RawConfigParser()
        c.read(os.path.join(self.path, 'metadata.ini'))
        self.title = c['metadata'].get('title')
        self.year = c['metadata'].get('year')
        self.emulator_start = c['metadata'].get('emulator_start')
        self.dosbox_conf = c['metadata'].get('dosbox_conf')
        self.urls = c['metadata'].get('url').split()
        self.configured = True

    def __gt__(self, other):
        return self.identifier.lower() > other.identifier.lower()

    def __lt__(self, other):
        return self.identifier.lower() < other.identifier.lower()

    def start(self, autorun=True):
        """
        Start the game in one of two modes:

        1. autorun=True

            Paste the contents of `emulator_start` into dosbox.bat, and
            run it. Dosbox will exit when the game ends.

        2. autorun=False

            Do as above, but don't run dosbox.bat and don't exit
            Dosbox. When Dosbox finishes, any changes made to
            dosbox.bat will be saved to the `emulator_start` variable
            in metadata.ini.

        The frontend allows starting the game in the second mode by pressing
        Alt-Enter. This allows the user to do the following from within dosbox:

            C:\> echo MYGAME.BAT >> dosbox.bat
            C:\> exit

        These changes will then be preserved for the next time the game
        is run normally.

        """
        batfile = os.path.join(self.gamedir, 'dosbox.bat')
        conffile = os.path.join(self.gamedir, 'dosbox.conf')
        dosbox_args = [self.gamedir, '-fullscreen']

        if self.dosbox_conf:
            with open(conffile, 'w') as f:
                f.write(self.dosbox_conf)
            dosbox_args.extend(['-userconf', '-conf', 'dosbox.conf'])

        if self.emulator_start:
            if autorun:
                dosbox_args[0] = os.path.join(self.gamedir, 'dosbox.bat')
                with open(batfile, 'w') as f:
                    f.write('@echo off\ncls\n')
                    f.write(self.emulator_start)

                if not '\n' in self.emulator_start:
                    startfile = os.path.join(self.gamedir, os.path.normpath(self.emulator_start))
                    if os.path.isfile(startfile):

                        # Special case for many games that currently only
                        # contain the name of the executable
                        dosbox_args[0] = startfile

            else:
                with open(batfile, 'w') as f:
                    f.write(self.emulator_start)

        else:
            autorun = False
            if not os.path.isfile(batfile):

                # Provide empty dosbox.bat for easy autocomplete
                # (and correct filename capitalization!)
                with open(batfile, 'w') as f:
                    f.write('\n')

        if autorun:
            dosbox_args.append('-exit')

        # Save our work and hand the game over to the Dosbox thread
        self.batfile = batfile
        self.autorun = autorun
        self.dosbox_args = dosbox_args
        DOSBox(self).start()


    def write_metadata(self):
        if self.title:
            self.config['metadata']['title'] = self.title
        if self.year:
            self.config['metadata']['year'] = self.year
        if self.urls:
            self.config['metadata']['url'] = '\n'.join(self.urls)
        if self.emulator_start:
            self.config['metadata']['emulator_start'] = self.emulator_start
        if self.dosbox_conf:
            self.config['metadata']['dosbox_conf'] = self.dosbox_conf
        inifile = os.path.join(self.path, 'metadata.ini')
        with open(inifile, 'w') as f:
            self.config.write(f)

    def get_titlescreen(self):
        path = os.path.join(self.path, 'title.png')
        if os.path.isfile(path):
            return path
        else:
            return None

    def is_ready(self):
        if not self.configured:
            try:
                self.configure()
            except:
                return False
        return os.path.isdir(self.gamedir)

    def get_size(self):
        return sum(os.path.getsize(os.path.join(self.path, f)) for f in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, f)))/1000000

    def reset(self):
        try:
            shutil.rmtree(self.gamedir)
        except:
            pass

    def download(self):
        if not self.configured:
            try:
                self.configure()
            except:
                return
        self.download_thread = Download(self.urls, self.gamedir)
        self.download_thread.start()

    def download_in_progress(self):
        if self.configured and self.download_thread:
            return self.download_thread.is_alive()

    def download_completed(self):
        return not self.download_in_progress()


class DOSBox(Thread):
    def __init__(self, game):
        self.game = game
        super().__init__(daemon=True)

    def run(self):
        game = self.game
        command = DOSBOX + game.dosbox_args
        print('Executing:', ' '.join(command))
        subprocess.run(command, capture_output=True)

        if not game.autorun:
            if os.path.isfile(game.batfile):
                with open(game.batfile, 'r') as f:
                    game.emulator_start = f.read()
                    if game.emulator_start:
                        game.write_metadata()


class Download(Thread):
    def __init__(self, urls, gamedir):
        self.urls = urls
        self.gamedir = gamedir
        super().__init__(daemon=True)

    def run(self):
        for u in self.urls:
            filename = unquote(u.split('/')[-1]).split('/')[-1]
            dest = os.path.join(os.path.dirname(self.gamedir), filename)
            if not os.path.isfile(dest):
                print(f'Downloading {u}...', end='', flush=True)
                request.urlretrieve(u, dest)
                print('done!')
            if filename.endswith('zip') or filename.endswith('ZIP') or filename.endswith('play'):
                print(f'Extracting {filename}...', end='', flush=True)
                try:
                    self.unzip(dest)
                    print('done!')
                except:
                    print('failed.')
            else:
                os.makedirs(self.gamedir, exist_ok=True)
                shutil.copy(dest, self.gamedir)

    def unzip(self, zipfile):
        with ZipFile(zipfile, 'r') as f:
            f.extractall(self.gamedir)
