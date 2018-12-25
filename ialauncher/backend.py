#!/usr/bin/env python3
import os
from threading import Thread
from natsort import natsorted as sorted
from jinja2 import Template
from urllib.parse import unquote
from socketserver import TCPServer, StreamRequestHandler

from .game import Game

template_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template.html')

class Backend(TCPServer):
    allow_reuse_address = True
    games = {}

    def __init__(self, games_dir, letter=None, aspect=False, slideshow=None):
        self.letter = letter
        self.aspect = aspect
        self.slideshow = slideshow
        self.load_games(games_dir)
        super().__init__(('localhost', 11236), GameHandler)

    def load_games(self, games_dir):
        print('Loading games', end='')
        for entry in os.listdir(games_dir):
            if not os.path.isdir(os.path.join(games_dir, entry)):
                continue
            try:
                game = Game(os.path.join(games_dir, entry))
                self.games[game.identifier] = game
                print('.', end='', flush=True)
            except:
                raise ValueError('Unable to load', entry)
        print('')
        if not self.games:
            print('No games found!')
            exit(1)

    def get_games(self):
        if self.letter:
            return [game for game in sorted(self.games.values(), key=lambda g: g.title.lower()) if (game.title[0].lower() in self.letter)]
        else:
            return [game for game in sorted(self.games.values(), key=lambda g: g.title.lower())]

    def start(self):
        thread = Thread(target=self.serve_forever)
        thread.daemon = True
        thread.start()

    def end(self):
        self.shutdown()


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
            initial_grid = 20
            aspect = self.server.aspect
            if self.server.slideshow:
                slideshow = self.server.slideshow * 1000
                initial_grid = 100
            else:
                slideshow = False
            self.wfile.write(T.render({
                'games': games_list,
                'initial_grid': initial_grid,
                'aspect': aspect,
                'slideshow': slideshow,
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

            if action == 'title.png':
                image = game.get_titlescreen()
                if image:
                    self.wfile.write(b'HTTP/1.0 200 OK\n')
                    self.wfile.write(b'Content-Type: image/png\n\n')
                    with open(image, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    return self.http_404()

            if action == 'start':
                game.start(autorun=True)

            if action == 'edit':
                game.start(autorun=False)
