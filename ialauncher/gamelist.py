"""The list of games."""

import random
from pathlib import Path

import pygame as pg

from .game import Game


class Gamelist:
    """The list of games."""

    def __init__(self) -> None:
        """Start with an empty list."""
        self.all_games: list[Game] = []
        self.ready_games = self.all_games  # The games to be shown, pre-filter
        self.games = self.all_games  # The games to be shown, post-filter
        self.ready: bool | None = None
        self.current_game = 0
        self.query = ""

    def add(self, game_dir: Path) -> None:
        """Add the game in the given directory."""
        self.all_games.append(Game(game_dir))

    def sort(self) -> None:
        """Sort the games by identifier, ignoring case."""
        self.all_games.sort(key=lambda game: game.identifier.lower())

    def show_ready(self, *, ready: bool | None) -> None:
        """Show only the games that are (not) ready to play, or all games (None).

        If no game matches, show all games. Keep the filter, unless no
        ready game matches it.
        """
        ready_games = [g for g in self.all_games if g.is_ready() == ready]
        self.ready = ready if ready_games else None
        self.ready_games = ready_games or self.all_games
        games = self.matching(self.query)
        if not games:
            self.query = ""
        self.show(games or self.ready_games)

    def show(self, games: list[Game]) -> None:
        """Show the given games; keep the current game, or select the next one."""
        current = self.get_current_game().identifier.lower()
        self.games = games
        self.current_game = next(
            (i for i, g in enumerate(self.games) if g.identifier.lower() >= current),
            0,
        )

    def matching(self, query: str) -> list[Game]:
        """Return the ready games whose identifier contains the query, ignoring case."""
        query = query.lower()
        return [g for g in self.ready_games if query in g.identifier.lower()]

    def add_to_filter(self, char: str) -> bool:
        """Add a character to the filter, unless no ready game would match.

        Return whether the character was added.
        """
        games = self.matching(self.query + char)
        if not games:
            return False
        self.query += char
        self.show(games)
        return True

    def clear_filter(self) -> None:
        """Show all ready games again."""
        if self.query:
            self.query = ""
            self.show(self.ready_games)

    def get_image(self, game: Game) -> pg.Surface:
        """Return the title screen of the given game."""
        if game.cached_image is None:
            game.cached_image = pg.image.load(game.titlescreen)
        return game.cached_image

    def get_current_game(self) -> Game:
        """Return the current game."""
        return self.games[self.current_game]

    def next_game(self) -> None:
        """Move to the next game, wrapping around at the end."""
        self.current_game = (self.current_game + 1) % len(self.games)

    def previous_game(self) -> None:
        """Move to the previous game, wrapping around at the start."""
        self.current_game = (self.current_game - 1) % len(self.games)

    def random_game(self) -> None:
        """Jump to a random game."""
        self.current_game = random.randrange(len(self.games))  # noqa: S311
