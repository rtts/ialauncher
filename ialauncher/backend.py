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

screenshotsdir = os.path.join(os.path.expanduser("~"), '.dosbox', 'capture')
template_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template.html')

class Backend(TCPServer):
    allow_reuse_address = True
    games = {}

    def __init__(self, games_dir, edit=False, letter=None):
        self.edit = edit
        self.letter = letter
        self.load_games(games_dir)
        super().__init__(('localhost', 11236), GameHandler)

    def load_games(self, games_dir):
        for entry in os.listdir(games_dir):
            if not os.path.isdir(os.path.join(games_dir, entry)):
                continue
            if self.letter and not entry[0].lower() in self.letter:
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
            return [game for game in sorted(self.games.values(), key=lambda g: g.title.lower()) if (not game.hidden) or self.edit]
        else:
            return [game for game in sorted(self.games.values(), key=lambda g: g.title.lower()) if (game.title[0].lower() in self.letter) and ((not game.hidden) or self.edit)]

    def start(self):
        thread = Thread(target=self.serve_forever)
        thread.daemon = True
        thread.start()

    def end(self):
        self.shutdown()

class Game:
    def __init__(self, path):
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
        self.emulator_start = c['metadata'].get('emulator_start')
        self.dosbox_conf = c['metadata'].get('dosbox_conf')

        # REMOVE ME!
        #self.dosbox_conf = '\n[dos]\nems = false'

        self.url = c['metadata'].get('url')
        if self.url:
            self.url = self.url.split()

            # todo: remove me!
            for u in self.url:
                if 'DOS.Memories.Project' in u:
                    self.dosmemories = True

    def rename(self, newname):
        dirname, oldname = os.path.split(self.path)
        newpath = os.path.join(dirname, newname)
        if os.path.exists(newpath):
            raise ValueError('Cannot rename, requested name already exists!')
        else:
            self.title = newname
            self.write_metadata()
            os.rename(self.path, newpath)
            self.__init__(newpath)

    def hide(self):
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

    def start(self, autorun=True):
        if not os.path.isdir(self.gamedir):
            self.download_files()
        os.chdir(self.gamedir)
        batfile = os.path.join(self.gamedir, 'dosbox.bat')
        conffile = os.path.join(self.gamedir, 'dosbox.conf')
        dosbox_args = ['-fullscreen']
        dosbox_run = '.'

        if self.dosbox_conf:
            with open(conffile, 'w') as f:
                f.write(self.dosbox_conf)
            dosbox_args.append('-userconf')
            dosbox_args.append('-conf dosbox.conf')

        if self.emulator_start:
            if os.path.isfile(self.emulator_start):
                dosbox_run = self.emulator_start
            else:
                with open(batfile, 'w') as f:
                    if autorun:
                        f.write('@echo off\ncls\n')
                    f.write(self.emulator_start)
                dosbox_run = 'dosbox.bat'
        else:
            open(batfile, 'a').close()

        if autorun:
            dosbox_args.append('-exit')
        else:
            dosbox_run = '.'
            open(batfile, 'a').close()

        os.system('dosbox {} {}'.format(dosbox_run, ' '.join(dosbox_args)))

        if not autorun:
            if os.path.isfile(batfile):
                with open(batfile, 'r') as f:
                    self.emulator_start = f.read()
                    if self.emulator_start:
                        self.write_metadata()

        # TODO: Indent me!
        if os.listdir(screenshotsdir):
            os.system('eog --fullscreen "{}"/*'.format(screenshotsdir))
            title_screens = sorted(os.listdir(screenshotsdir))
            if title_screens:
                os.rename(os.path.join(screenshotsdir, title_screens[0]), os.path.join(self.path, 'title.png'))
                shutil.rmtree(screenshotsdir)
                os.mkdir(screenshotsdir)


    def download_files(self, autorun=True):
        os.chdir(self.path)
        for u in self.url:
            filename = unquote(u.split('/')[-1])
            if not os.path.isfile(filename):
                print('Downloading', filename)
                request.urlretrieve(u, filename)
            if filename.endswith('zip') or filename.endswith('ZIP') or filename.endswith('play'):
                print('Extracting', filename)
                self.extract_file(filename)
            else:
                os.makedirs(self.gamedir, exist_ok=True)
                shutil.copy(filename, self.gamedir)

    def extract_file(self, zipfile):
        with ZipFile(zipfile, 'r') as f:
            f.extractall(self.gamedir)
        if os.path.isfile(os.path.join(self.gamedir, 'dosbox.conf')):
            os.remove(os.path.join(self.gamedir, 'dosbox.conf'))

    def write_metadata(self):
        if self.title:
            self.config['metadata']['title'] = self.title
        if self.year:
            self.config['metadata']['year'] = self.year
        if self.url:
            self.config['metadata']['url'] = '\n'.join(self.url)
        if self.emulator_start:
            self.config['metadata']['emulator_start'] = self.emulator_start
        if self.dosbox_conf:
            self.config['metadata']['dosbox_conf'] = self.dosbox_conf
        inifile = os.path.join(self.path, 'metadata.ini')
        with open(inifile, 'w') as f:
            self.config.write(f)

    def get_titlescreen(self):
        for candidate in ['title.png', '00_coverscreenshot.jpg']:
            path = os.path.join(self.path, candidate)
            if os.path.isfile(path):
                return path
        return None

    def urlencoded(self):
        return quote(self.identifier)

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

            if action == 'start':
                game.start(autorun=True)

            if action == 'edit':
                game.start(autorun=False)

            if action == 'rename':
                while self.rfile.readline().strip():
                    pass
                newname = self.rfile.readline().decode('utf8').strip()
                game.rename(newname)
