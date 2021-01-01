import os
import random
import pygame as pg

from .game import Game

class GameList:
    games = []
    current_game = 0

    def add(self, game_dir):
        try:
            self.games.append(Game(game_dir))
        except:
            print('Error loading', os.path.basename(game_dir))

    def sort(self, slideshow):
        self.games.sort()
        if slideshow:
            self.current_game = random.randrange(len(self.games))

    def get_image(self):
        game = self.get_current_game()
        if not hasattr(game, 'cached_image'):
            game.cached_image = pg.image.load(game.get_titlescreen())
        return game.cached_image

    def get_current_game(self):
        return self.games[self.current_game]

    def next_letter(self):
        '''Jump to the next game with different letter'''
        letter = self.get_current_game().identifier.lower()[0]
        for game in self.games[self.current_game:]:
            if not game.identifier.lower().startswith(letter):
                break
            self.current_game += 1
        if self.current_game >= len(self.games):
            self.current_game = 0

    def previous_letter(self):
        '''Jump to the first game that starts with previous game's letter'''
        letter = self.games[(self.current_game - 1) % len(self.games)].identifier.lower()[0]
        for i, game in enumerate(self.games):
            if game.identifier.lower().startswith(letter):
                self.current_game = i
                break

    def next_game(self):
        self.current_game = (self.current_game + 1) % len(self.games)

    def previous_game(self):
        self.current_game = (self.current_game - 1) % len(self.games)

    def random_game(self):
        self.current_game = random.randrange(len(self.games))

    def letter(self, letter):
        '''Jump to specific letter'''
        for i, game in enumerate(self.games):
            if game.identifier.lower().startswith(letter):
                self.current_game = i
                break
