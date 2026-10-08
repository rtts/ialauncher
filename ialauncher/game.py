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

            C:\\> echo MYGAME.BAT >> dosbox.bat
            C:\\> exit

        These changes will then be preserved for the next time the game
        is run normally.

        """
        batfile = os.path.join(self.gamedir, 'dosbox.bat')
        conffile = os.path.join(self.gamedir, 'dosbox.conf')
        dosbox_args = [".", '-userconf']  # Use --nolocalconf for DOSBox Staging

        if self.dosbox_conf:
            with open(conffile, 'w') as f:
                f.write(self.dosbox_conf)
            dosbox_args.extend(['-conf', 'dosbox.conf'])

        if self.emulator_start:
            if autorun:
                dosbox_args[0] = 'dosbox.bat'
                with open(batfile, 'w') as f:
                    f.write('@echo off\ncls\n')
                    f.write(self.emulator_start)

                if not '\n' in self.emulator_start:
                    if os.path.isfile(os.path.join(self.gamedir, os.path.normpath(self.emulator_start))):

                        # Special case for many games that currently only
                        # contain the name of the executable
                        dosbox_args[0] = self.emulator_start

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
        subprocess.run(command, cwd=game.gamedir, capture_output=True)

        if not game.autorun:
            if os.path.isfile(game.batfile):
                with open(game.batfile, 'r') as f:
                    game.emulator_start = f.read().rstrip('\r\n')
                    if game.emulator_start:
                        game.write_metadata()


class Download(Thread):
    def __init__(self, urls, gamedir):
        self.urls = urls
        self.gamedir = gamedir
        self.status = ''
        super().__init__(daemon=True)

    def run(self):
        for i, u in enumerate(self.urls, 1):
            filename = unquote(u.split('/')[-1]).split('/')[-1]
            dest = os.path.join(os.path.dirname(self.gamedir), filename)
            prefix = f'[{i}/{len(self.urls)}] ' if len(self.urls) > 1 else ''
            if not os.path.isfile(dest):
                print(f'Downloading {u}...', end='', flush=True)
                action = f'{prefix}Downloading {filename}'
                self.report(action, 0, 0)
                request.urlretrieve(u, dest, lambda blocks, size, total: self.report(action, blocks * size, total))
                print('done!')
            if filename.lower().endswith(('.zip', '.play')):
                print(f'Unzipping {filename}...', end='', flush=True)
                try:
                    self.unzip(dest, f'{prefix}Unzipping {filename}')
                    print('done!')
                except:
                    print('failed.')
            else:
                os.makedirs(self.gamedir, exist_ok=True)
                shutil.copy(dest, self.gamedir)

    def report(self, action: str, done: int, total: int) -> None:
        if total > 0:
            done = min(done, total)
            self.status = f'{action} ({done / 1e6:.1f} / {total / 1e6:.1f} MB, {done * 100 // total}%)'
        else:
            self.status = f'{action} ({done / 1e6:.1f} MB)'

    def unzip(self, zipfile: str, action: str) -> None:
        with ZipFile(zipfile, 'r') as f:
            members = f.infolist()
            total = sum(m.file_size for m in members)
            done = 0
            for m in members:
                self.report(action, done, total)
                f.extract(m, self.gamedir)
                done += m.file_size
