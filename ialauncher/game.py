import os, sys
import shutil
import subprocess
from zipfile import ZipFile
from urllib import request
from urllib.error import ContentTooShortError
from urllib.parse import unquote
from configparser import RawConfigParser
from threading import Thread

from .dosbox import get_dosbox_path
from .scummvm import get_scummvm_path, ScummVMNotFound
from .iso import ISOFile
from . import options

DOSBOX = get_dosbox_path()
SCUMMVM = None

class Game:
    def __init__(self, path):
        self.path = path
        self.identifier = os.path.basename(path)
        self.configured = False
        self.download_thread = None

    def configure(self):
        self.config = c = RawConfigParser()
        c.read(os.path.join(self.path, 'metadata.ini'))
        self.title = c['metadata'].get('title')
        self.year = c['metadata'].get('year')
        self.engine = c['metadata'].get('engine', 'dosbox')
        self.scummvm_game = c['metadata'].get('scummvm_game')
        self.scummvm_args = (c['metadata'].get('scummvm_args') or '').split()
        datadir = 'scummvm_data' if self.engine == 'scummvm' else 'dosbox_drive_c'
        self.gamedir = os.path.join(self.path, datadir)
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
        if self.engine == 'scummvm':
            return self.start_scummvm(autorun)

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
        self.emulator_args = dosbox_args
        self.emulator_thread = DOSBox(self)
        self.emulator_thread.start()

    def start_scummvm(self, autorun=True):
        """
        Start the game with ScummVM, using `scummvm_game` as the
        target. Savegames are stored in the game directory. With
        autorun=False, the ScummVM launcher is opened instead.

        """
        global SCUMMVM
        if SCUMMVM is None:
            try:
                SCUMMVM = get_scummvm_path()
            except ScummVMNotFound as e:
                print(e)
                return

        captures_dir = os.path.expanduser(options.captures_dir)
        os.makedirs(captures_dir, exist_ok=True)
        args = ['--path=.', '--savepath=.', f'--screenshotpath={captures_dir}']
        if autorun and self.scummvm_game:
            args.extend(self.scummvm_args + [self.scummvm_game])

        self.emulator_args = args
        self.emulator_thread = Emulator(self, SCUMMVM)
        self.emulator_thread.start()

    def is_running(self):
        return bool(getattr(self, 'emulator_thread', None)) and self.emulator_thread.is_alive()


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
        if not self.is_ready():
            return
        try:
            shutil.rmtree(self.gamedir)
        except:
            pass

    def download(self, unzip: bool = True):
        if not self.configured:
            try:
                self.configure()
            except:
                return
        # ScummVM can't read disc images, so extract them. DOSBox games
        # mount their disc images themselves.
        extract = self.engine == 'scummvm'
        self.download_thread = Download(self.urls, self.gamedir, unzip, extract)
        self.download_thread.start()

    def download_in_progress(self):
        if self.configured and self.download_thread:
            return self.download_thread.is_alive()

    def download_completed(self):
        return not self.download_in_progress()


class Emulator(Thread):
    def __init__(self, game, executable):
        self.game = game
        self.executable = executable
        super().__init__(daemon=True)

    def run(self):
        game = self.game
        command = self.executable + game.emulator_args
        print('Executing:', ' '.join(command))
        subprocess.run(command, cwd=game.gamedir, capture_output=True)


class DOSBox(Emulator):
    def __init__(self, game):
        super().__init__(game, DOSBOX)

    def run(self):
        super().run()
        game = self.game

        if not game.autorun:
            if os.path.isfile(game.batfile):
                with open(game.batfile, 'r') as f:
                    game.emulator_start = f.read().rstrip('\r\n')
                    if game.emulator_start:
                        game.write_metadata()


class Download(Thread):
    def __init__(self, urls, gamedir, unzip: bool = True, extract: bool = False):
        self.urls = urls
        self.gamedir = gamedir
        self.should_unzip = unzip
        self.should_extract = extract
        self.status = ''
        super().__init__(daemon=True)

    def run(self):
        for i, u in enumerate(self.urls, 1):
            filename = unquote(u.split('/')[-1]).split('/')[-1]
            dest = os.path.join(os.path.dirname(self.gamedir), filename)
            prefix = f'[{i}/{len(self.urls)}] ' if len(self.urls) > 1 else ''
            if not os.path.isfile(dest):
                print(f'Downloading {u}... ', end='', flush=True)
                action = f'{prefix}Downloading {filename}'
                self.report(action, 0, 0)
                self.request(u, dest, action)
                print('done!')
            if not self.should_unzip:
                continue
            if self.should_extract and filename.lower().endswith(('.iso', '.bin')):
                print(f'Extracting {filename}... ', end='', flush=True)
                try:
                    self.extract_iso(dest, f'{prefix}Extracting {filename}')
                    print('done!')
                except:
                    print('failed.')
            elif filename.lower().endswith(('.zip', '.play')):
                print(f'Unzipping {filename}... ', end='', flush=True)
                try:
                    self.unzip(dest, f'{prefix}Unzipping {filename}')
                    print('done!')
                except:
                    print('failed.')
            else:
                os.makedirs(self.gamedir, exist_ok=True)
                shutil.copy(dest, self.gamedir)

    def request(self, url: str, dest: str, action: str) -> None:
        try:
            with request.urlopen(url, timeout=60) as response, open(dest, 'wb') as f:
                total = int(response.headers.get('Content-Length') or 0)
                done = 0
                while block := response.read(1024*8):
                    f.write(block)
                    done += len(block)
                    self.report(action, done, total)
            if done < total:
                raise ContentTooShortError(f'Download failed: got only {done} out of {total} bytes', None)
        except BaseException:
            if os.path.isfile(dest):
                os.remove(dest)
            raise

    def report(self, action: str, done: int, total: int) -> None:
        if total > 0:
            done = min(done, total)
            self.status = f'{action} ({done / 1e6:.1f} / {total / 1e6:.1f} MB, {done * 100 // total}%)'
        else:
            self.status = action

    def unzip(self, zipfile: str, action: str) -> None:
        with ZipFile(zipfile, 'r') as f:
            members = f.infolist()
            total = sum(m.file_size for m in members)
            done = 0
            for m in members:
                self.report(action, done, total)
                f.extract(m, self.gamedir)
                done += m.file_size

    def extract_iso(self, isofile: str, action: str) -> None:
        with ISOFile(isofile) as iso:
            members = list(iso.walk())
            total = sum(size for _, _, size in members)
            done = 0
            def progress(n):
                nonlocal done
                done += n
                self.report(action, done, total)
            for path, sector, size in members:
                iso.extract(sector, size, os.path.join(self.gamedir, path), progress)
