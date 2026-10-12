import os
import random

import pygame as pg

from .game import Game

SEARCH_TIMEOUT = 1000


class GameList:
    current_game = 0
    query = ""
    last_keypress = 0

    def __init__(self) -> None:
        self.games: list[Game] = []

    def add(self, game_dir: str) -> None:
        try:
            self.games.append(Game(game_dir))
        except:
            print("Error loading", os.path.basename(game_dir))

    def sort(self, slideshow: int) -> None:
        self.games.sort()
        self.current_game = random.randrange(len(self.games))

    def get_image(self, game: Game | None = None) -> pg.Surface:
        if game is None:
            game = self.get_current_game()
        if game.cached_image is None:
            path = game.get_titlescreen()
            assert path is not None, f"{game.identifier} has no title screen"
            game.cached_image = pg.image.load(path)
        return game.cached_image

    def get_current_game(self) -> Game:
        return self.games[self.current_game]

    def next_letter(self) -> None:
        """Jump to the next game with different letter"""
        letter = self.get_current_game().identifier.lower()[0]
        for game in self.games[self.current_game :]:
            if not game.identifier.lower().startswith(letter):
                break
            self.current_game += 1
        if self.current_game >= len(self.games):
            self.current_game = 0

    def previous_letter(self) -> None:
        """Jump to the first game that starts with previous game's letter"""
        letter = self.games[
            (self.current_game - 1) % len(self.games)
        ].identifier.lower()[0]
        for i, game in enumerate(self.games):
            if game.identifier.lower().startswith(letter):
                self.current_game = i
                break

    def next_game(self) -> None:
        self.current_game = (self.current_game + 1) % len(self.games)

    def previous_game(self) -> None:
        self.current_game = (self.current_game - 1) % len(self.games)

    def random_game(self) -> None:
        self.current_game = random.randrange(len(self.games))

    def is_searching(self) -> bool:
        return (
            bool(self.query)
            and pg.time.get_ticks() - self.last_keypress <= SEARCH_TIMEOUT
        )

    def reset_search(self) -> None:
        self.query = ""

    def search(self, char: str) -> None:
        if not self.is_searching():
            self.reset_search()
        self.last_keypress = pg.time.get_ticks()
        self.find(self.query + char)

    def backspace(self) -> None:
        if not self.is_searching():
            self.reset_search()
            return
        self.last_keypress = pg.time.get_ticks()
        self.query = self.query[:-1]
        if self.query:
            self.find(self.query)

    def find(self, query: str) -> None:
        for i, game in enumerate(self.games):
            if game.identifier.lower().startswith(query.lower()):
                self.current_game = i
                self.query = query
                break
