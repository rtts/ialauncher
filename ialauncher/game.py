import os, sys
import shutil
import subprocess
from zipfile import ZipFile
from urllib import request
from urllib.parse import quote, unquote
from configparser import RawConfigParser
from multiprocessing import Process, Queue
from queue import Empty

from .dosbox import get_dosbox_path

DOSBOX = get_dosbox_path()

class Game:
    def __init__(self, path):
        self.path = path
        self.gamedir = os.path.join(self.path, 'dosbox_drive_c')
        self.identifier = os.path.basename(path)
        self.config = c = RawConfigParser()
        c.read(os.path.join(path, 'metadata.ini'))
        self.title = c['metadata'].get('title')
        self.year = c['metadata'].get('year')
        self.emulator_start = c['metadata'].get('emulator_start')
        self.dosbox_conf = c['metadata'].get('dosbox_conf')
        self.urls = c['metadata'].get('url').split()

    def __gt__(self, other):
        return self.identifier > other.identifier

    def __lt__(self, other):
        return self.identifier < other.identifier

    def start(self, autorun=True):
        """
        Start the game in one of two modes:

        1. autorun=True

            Paste the contents of `emulator_start` into dosbox.bat, and
            run it. Dosbox will exit when the game ends.

        2. autorun=False

            Do as above, but don't run dosbox.bat and don't exit Dosbox.
            Any changes made to dosbox.bat will be save as the
            `emulator_start` variable in metadata.ini.

        The frontend allows starting the game in the second mode by pressing
        Alt-Enter. This allows the user to do the following from within dosbox:

            C:\> echo MYGAME.BAT >> dosbox.bat
            C:\> exit

        These changes will then be preserved for the next time the game
        is run normally. Make sure to commit any useful additions!

        """

        # Optionally, set the `autorun` attribute before starting the game
        if hasattr(self, 'autorun'):
            autorun = self.autorun

        batfile = os.path.join(self.gamedir, 'dosbox.bat')
        conffile = os.path.join(self.gamedir, 'dosbox.conf')
        dosbox_args = ['-fullscreen']
        dosbox_run = self.gamedir

        if self.dosbox_conf:
            with open(conffile, 'w') as f:
                f.write(self.dosbox_conf)
            dosbox_args.extend(['-userconf', '-conf', 'dosbox.conf'])

        if self.emulator_start:
            if autorun:
                if os.path.isfile(os.path.join(self.gamedir, os.path.normpath(self.emulator_start))):

                    # Special case for many games that currently only
                    # contain the name of the executable
                    dosbox_run = os.path.join(self.gamedir, os.path.normpath(self.emulator_start))

                else:
                    dosbox_run = os.path.join(self.gamedir, 'dosbox.bat')
                    with open(batfile, 'w') as f:
                        f.write('@echo off\ncls\n')
                        f.write(self.emulator_start)

            else:
                with open(batfile, 'w') as f:
                    f.write(self.emulator_start)

        else:
            autorun = False
            if not os.path.isfile(batfile):
                with open(batfile, 'w') as f:
                    f.write('\n')

        if autorun:
            dosbox_args.append('-exit')

        command = [DOSBOX, dosbox_run] + dosbox_args
        child_process = subprocess.Popen(command)

        if not autorun and sys.platform != 'win32':
            # The wait() function will make Windows spawn new
            # instances of DOSBox over and over...
            child_process.wait()
            if os.path.isfile(batfile):
                with open(batfile, 'r') as f:
                    self.emulator_start = f.read()
                    if self.emulator_start:
                        self.write_metadata()

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
        return os.path.isdir(self.gamedir)

    def get_size(self):
        return sum(os.path.getsize(os.path.join(self.path, f)) for f in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, f)))/1000000

    def reset(self):
        try:
            shutil.rmtree(self.gamedir)
        except:
            pass

    def download(self):
        self.finished = False
        self.q = Queue()
        Download(self.urls, self.gamedir, self.q).start()

    def download_completed(self):
        if self.finished:
            return True
        try:
            self.q.get(block=False, timeout=1)
            self.finished = True
            return True
        except Empty:
            return False

class Download(Process):
    def __init__(self, urls, gamedir, q):
        super().__init__()
        self.urls = urls
        self.gamedir = gamedir
        self.q = q

    def run(self):
        for u in self.urls:
            filename = unquote(u.split('/')[-1])
            dest = os.path.join(os.path.dirname(self.gamedir), filename)
            if not os.path.isfile(dest):
                print(f'Downloading {u}...', end='', flush=True)
                request.urlretrieve(u, dest)
                print('done!')
            if filename.endswith('zip') or filename.endswith('ZIP') or filename.endswith('play'):
                print(f'Extracting {filename}...', end='', flush=True)
                self.unzip(dest)
                print('done!')
            else:
                os.makedirs(self.gamedir, exist_ok=True)
                shutil.copy(dest, self.gamedir)
        self.q.put("Done!")

    def unzip(self, zipfile):
        with ZipFile(zipfile, 'r') as f:
            f.extractall(self.gamedir)
