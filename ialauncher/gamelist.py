"""The list of games."""

import random
from pathlib import Path

import pygame as pg

from .game import Game

SEARCH_TIMEOUT = 1000


class GameList:
    """The list of games."""

    current_game = 0
    query = ""
    last_keypress = 0

    def __init__(self) -> None:
        """Start with an empty list."""
        self.games: list[Game] = []

    def add(self, game_dir: Path) -> None:
        """Add the game in the given directory."""
        self.games.append(Game(game_dir))

    def sort(self) -> None:
        """Sort the games by identifier and select a random one."""
        self.games.sort()
        self.random_game()

    def get_image(self, game: Game | None = None) -> pg.Surface:
        """Return the title screen of the given (or current) game."""
        if game is None:
            game = self.get_current_game()
        if game.cached_image is None:
            path = game.get_titlescreen()
            if path is None:
                msg = f"{game.identifier} has no title screen"
                raise ValueError(msg)
            game.cached_image = pg.image.load(path)
        return game.cached_image

    def get_current_game(self) -> Game:
        """Return the current game."""
        return self.games[self.current_game]

    def next_letter(self) -> None:
        """Jump to the next game with different letter."""
        letter = self.get_current_game().identifier.lower()[0]
        for game in self.games[self.current_game :]:
            if not game.identifier.lower().startswith(letter):
                break
            self.current_game += 1
        if self.current_game >= len(self.games):
            self.current_game = 0

    def previous_letter(self) -> None:
        """Jump to the first game that starts with previous game's letter."""
        letter = self.games[
            (self.current_game - 1) % len(self.games)
        ].identifier.lower()[0]
        for i, game in enumerate(self.games):
            if game.identifier.lower().startswith(letter):
                self.current_game = i
                break

    def next_game(self) -> None:
        """Move to the next game, wrapping around at the end."""
        self.current_game = (self.current_game + 1) % len(self.games)

    def previous_game(self) -> None:
        """Move to the previous game, wrapping around at the start."""
        self.current_game = (self.current_game - 1) % len(self.games)

    def random_game(self) -> None:
        """Jump to a random game."""
        self.current_game = random.randrange(len(self.games))  # noqa: S311

    def is_searching(self) -> bool:
        """Return whether a search query was typed recently."""
        return (
            bool(self.query)
            and pg.time.get_ticks() - self.last_keypress <= SEARCH_TIMEOUT
        )

    def reset_search(self) -> None:
        """Forget the search query."""
        self.query = ""

    def search(self, char: str) -> None:
        """Add a character to the query and jump to the first match."""
        if not self.is_searching():
            self.reset_search()
        self.last_keypress = pg.time.get_ticks()
        self.find(self.query + char)

    def backspace(self) -> None:
        """Remove the last character of the query and jump to the first match."""
        if not self.is_searching():
            self.reset_search()
            return
        self.last_keypress = pg.time.get_ticks()
        self.query = self.query[:-1]
        if self.query:
            self.find(self.query)

    def find(self, query: str) -> None:
        """Jump to the first game that starts with the query, if any."""
        for i, game in enumerate(self.games):
            if game.identifier.lower().startswith(query.lower()):
                self.current_game = i
                self.query = query
                break
