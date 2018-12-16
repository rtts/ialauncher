#!/usr/bin/env python3
from threading import Thread

import os, re
import xml.etree.ElementTree as ET
import internetarchive
import random
import subprocess
import shutil
import time
from natsort import natsorted as sorted
from multiprocessing import Process
from zipfile import ZipFile
from urllib import request
from pathlib import Path
from jinja2 import Template
from urllib.parse import quote, unquote
from socketserver import TCPServer, StreamRequestHandler
from configparser import RawConfigParser

games_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'games')
midi_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'midi')
screenshotsdir = os.path.join(os.path.expanduser("~"), '.dosbox', 'capture')
template_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template.html')

class Backend(TCPServer):
    allow_reuse_address = True
    games = {}

    def __init__(self, edit=False, letter=None):
        self.edit = edit
        self.letter = letter.lower()
        self.load_games()
        super().__init__(('localhost', 11236), GameHandler)

    def load_games(self):
        for entry in os.listdir(games_dir):
            if not os.path.isdir(os.path.join(games_dir, entry)):
                continue
            if entry.startswith('.'):
                continue
            if self.letter and not entry.lower().startswith(self.letter):
                continue
            try:
                game = Game(os.path.join(games_dir, entry))
                self.games[game.identifier] = game
                print('.', end='', flush=True)
            except:
                raise ValueError('Unable to load', entry)
        print('')

    def get_games(self):
        if self.letter is None:
            return [game for game in sorted(self.games.values(), key=lambda g: g.title) if (not game.hidden) or self.edit]
        else:
            return [game for game in sorted(self.games.values(), key=lambda g: g.title) if game.title.lower().startswith(self.letter) and ((not game.hidden) or self.edit)]

    def start(self):
        thread = Thread(target=self.serve_forever)
        thread.daemon = True
        thread.start()
        self.start_music()

    def start_music(self):
        def play():
            while True:
                random_file = random.choice(os.listdir(midi_dir))
                time.sleep(1)
                self.process = subprocess.Popen(['timidity', '-A25,25', os.path.join(midi_dir, random_file)])
                if self.process.wait():
                    return
        thread = Thread(target=play)
        thread.daeomon = True
        thread.start()

    def stop_music(self):
        self.process.kill()

    def end(self):
        self.stop_music()
        self.shutdown()

class Game:
    def __init__(self, path):
        '''Initialize a game given its path

        '''
        self.path = path
        self.gamedir = os.path.join(self.path, 'dosbox_drive_c')
        entry = os.path.basename(path)
        if entry.startswith('.'):
            self.hidden = True
            self.identifier = entry.lstrip('.')
        else:
            self.hidden = False
            self.identifier = entry

        self.config = c = RawConfigParser()
        c.read(os.path.join(path, 'metadata.ini'))
        #self.title = c['metadata'].get('title')
        self.title = self.identifier
        self.year = c['metadata'].get('year')
        self.url = c['metadata'].get('url')
        self.emulator_start = c['metadata'].get('emulator_start')

        try: # TODO: remove me!
            if 'DOS.Memories.Project' in self.url:
                self.dosmemories = True
        except:
            pass

    def rename(self, newname):
        dirname, oldname = os.path.split(self.path)
        newpath = os.path.join(dirname, newname)
        if os.path.exists(newpath):
            raise ValueError('Cannot rename, requested name already exists!')
        else:
            os.rename(self.path, newpath)
            self.title = newname
            self.path = newpath
            self.write_metadata()

    def hide(self):
        '''Hides a game by prepending a dot (.) to the directory name.
           If the game is already hidden, unhide it.

        '''
        parent, entry = os.path.split(self.path)
        if not entry.startswith('.'):
            newpath = os.path.join(parent, '.' + self.identifier)
            os.rename(self.path, newpath)
            self.path = newpath
            self.hidden = True
        else:
            newpath = os.path.join(parent, self.identifier.lstrip('.'))
            os.rename(self.path, newpath)
            self.path = newpath
            self.hidden = False

    def extract_zipfile(self, zipfile):
        with ZipFile(zipfile, 'r') as f:
            f.extractall(self.gamedir)
        if os.path.isfile(os.path.join(self.gamedir, 'dosbox.conf')):
            os.remove(os.path.join(self.gamedir, 'dosbox.conf'))

    def find_existing_zipfile(self):
        '''Searches the game directory for a zipfile to extract

        '''
        def either(c):
            return '[{}{}]'.format(c.lower(), c.upper()) if c.isalpha() else c
        glob = '*.' + ''.join(either(char) for char in 'zip')
        zipfiles = list(Path(self.path).glob(glob))
        if len(zipfiles) == 0:
            return None
        elif len(zipfiles) > 1:
            raise IOError('Multiple zipfiles are present in the game directory!')
        else:
            return os.path.join(self.path, zipfiles[0])

    def prepare_game(self, autorun=True):
        '''Downloads the zipfile (if needed), extracts it (if needed) and
        starts the DOSBox emulator

        '''
        if not os.path.isdir(self.gamedir):
            zipfile = self.find_existing_zipfile()
            if zipfile is None:
                self.download_zipfile()
                zipfile = self.find_existing_zipfile()
                if zipfile is None:
                    raise IOError('Failed to download zipfile!')
            self.extract_zipfile(zipfile)

    def start(self, autorun=True):
        self.prepare_game()
        os.chdir(self.gamedir)
        batfile = os.path.join(self.gamedir, 'dosbox.bat')

        if self.emulator_start:
            if os.path.isfile(self.emulator_start):
                os.system('dosbox "{}" -exit -fullscreen'.format(self.emulator_start))
            else:
                with open(batfile, 'w') as f:
                    if autorun:
                        f.write('@echo off\ncls\n')
                    f.write(self.emulator_start)
                os.system('dosbox dosbox.bat -exit -fullscreen')# if autorun else os.system('dosbox .')
        else:
            os.system('dosbox .')

        if not autorun and os.path.isfile(batfile):
            with open(batfile, 'r') as f:
                self.emulator_start = f.read()
                self.write_metadata()

    def write_metadata(self):
        if self.title:
            self.config['metadata']['title'] = self.title
        if self.year:
            self.config['metadata']['year'] = self.year
        if self.url:
            self.config['metadata']['url'] = self.url
        if self.emulator_start:
            self.config['metadata']['emulator_start'] = self.emulator_start
        inifile = os.path.join(self.path, 'metadata.ini')
        with open(inifile, 'w') as f:
            self.config.write(f)

    def get_titlescreen(self):
        for candidate in ['title_screen.png', '00_coverscreenshot.jpg']:
            path = os.path.join(self.path, candidate)
            if os.path.isfile(path):
                return path
        return None

    def urlencoded(self):
        return quote(self.identifier)

    def download_zipfile(self):
        request.urlretrieve(self.url, os.path.join(self.path, self.title + '.zip'))

class DOSMemoriesGame(Game):
    def __init__(self, path):
        super().__init__(path)

class SoftwareLibraryGame(Game):
    pass

class GameHandler(StreamRequestHandler):
    def http_404(self):
        self.wfile.write(b'HTTP/1.0 404 Not Found\n')

    def handle(self):
        data = self.rfile.readline().strip().decode('utf8')
        path = unquote(data.split(' ')[1]).lstrip('/')

        if path == '':
            with open(template_file, 'r') as f:
                T = Template(f.read())
            self.wfile.write(b'HTTP/1.0 200 OK\n')
            self.wfile.write(b'Content-Type: text/html; charset=utf-8\n\n')
            games_list = self.server.get_games()
            if self.server.edit:
                initial_grid = 20
            else:
                initial_grid = 100
            self.wfile.write(T.render({
                'games': games_list,
                'edit': self.server.edit,
                'initial_grid': initial_grid,
            }).encode('utf8'))

        else:
            try:
                game_id, action = path.split('/')
            except:
                print('Error parsing request: GET', path)
            try:
                game = self.server.games[game_id]
            except:
                return self.http_404()

            if action == 'title_screen.jpg':
                image = game.get_titlescreen()
                if image:
                    self.wfile.write(b'HTTP/1.0 200 OK\n')
                    self.wfile.write(b'Content-Type: image/jpg\n\n')
                    with open(image, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    return self.http_404()

            if action == 'hide':
                if self.server.edit:
                    game.hide()

            if action == 'next_song':
                self.server.stop_music()
                self.server.start_music()

            if action == 'start':
                if not self.server.edit:
                    self.server.stop_music()

                game.start(autorun=not self.server.edit)

                if self.server.edit:
                    if type(game) == DOSMemoriesGame:
                        os.rename(os.path.join(game.gamedir, 'dosbox.bat'), os.path.join(game.path, 'dosbox.bat'))
                    if os.listdir(screenshotsdir):
                        os.system('eog --fullscreen "{}"/*'.format(screenshotsdir))
                        title_screens = sorted(os.listdir(screenshotsdir))
                        if title_screens:
                            os.rename(os.path.join(screenshotsdir, title_screens[0]), os.path.join(game.path, 'title_screen.png'))
                            shutil.rmtree(screenshotsdir)
                            os.mkdir(screenshotsdir)

                if not self.server.edit:
                    self.server.start_music()

            if action == 'rename':
                while self.rfile.readline().strip():
                    pass
                newname = self.rfile.readline().decode('utf8').strip()
                game.rename(newname)
