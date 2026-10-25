"""The list of games."""

import random
import traceback
from pathlib import Path
from threading import Event, Thread
from typing import override

import pygame as pg

from .game import Game
from .watcher import MetadataWatcher

GAMES_LOADED = pg.event.custom_type()
LOADING_FAILED = pg.event.custom_type()
BATCH_SIZE = 30


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
        self.loader: GameLoader | None = None
        self.watcher: MetadataWatcher | None = None

    def add(self, game_dir: Path, metadata: dict[str, str] | None = None) -> None:
        """Add the game in the given directory, without its title screen."""
        self.all_games.append(Game(game_dir, metadata))

    def sort(self) -> None:
        """Sort the games by identifier, ignoring case."""
        self.all_games.sort(key=lambda game: game.identifier.lower())

    def load_titlescreens(self) -> None:
        """Load the title screens in the background."""
        count = len(self.games)
        order = dict.fromkeys(
            (self.current_game + sign * step) % count
            for step in range(count // 2 + 1)
            for sign in (-1, 1)
        )
        self.loader = GameLoader([self.games[i] for i in order])
        self.loader.start()

    def stop_loading(self) -> None:
        """Stop loading the title screens, if that's still going on."""
        if self.loader:
            self.loader.stop()

    def watch(self) -> None:
        """Watch the metadata.ini files of all games for changes, on Linux."""
        self.watcher = MetadataWatcher([game.path for game in self.all_games])
        self.watcher.start()

    def stop_watching(self) -> None:
        """Stop watching the metadata.ini files, if that's going on."""
        if self.watcher:
            self.watcher.stop()
            self.watcher = None

    def changed_games(self) -> list[Game]:
        """Return the games whose metadata.ini changed since the last call."""
        if not self.watcher:
            return []
        changed = self.watcher.pop_changed()
        return [game for game in self.all_games if game.path in changed]

    def show_game(self, game: Game) -> None:
        """Show all games, without any filter, and select the given game."""
        self.query = ""
        self.show_ready(ready=None)
        self.current_game = self.games.index(game)

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

        # Update the current_game index to still point to the same
        # game, or the nearest one after it, or 0.
        self.current_game = next(
            (i for i, g in enumerate(self.games) if g.identifier.lower() >= current),
            0,
        )

    def matching(self, query: str) -> list[Game]:
        """Return the ready games whose identifier contains the query, ignoring case.

        Games whose year starts with the query match as well, so that
        typing a year shows all games from that year. A query that
        starts with ^ only matches the start of the identifier.
        """
        query = query.lower()
        if query.startswith("^"):
            prefix = query[1:]
            return [
                g
                for g in self.ready_games
                if g.identifier.lower().startswith(prefix) or g.year.startswith(prefix)
            ]
        return [
            g
            for g in self.ready_games
            if query in g.identifier.lower() or g.year.startswith(query)
        ]

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


class GameLoader(Thread):
    """A thread that loads the title screens of games.

    After every BATCH_SIZE games, and after the last one, it posts
    GAMES_LOADED, so that the scene draws the new thumbnails.
    If a title screen can't be loaded, it posts LOADING_FAILED
    with the traceback, and stops.
    """

    def __init__(self, games: list[Game]) -> None:
        """Prepare to load the title screens of the games, in order."""
        self.games = games
        self.stopped = Event()
        super().__init__(daemon=True)

    @override
    def run(self) -> None:
        """Load the title screens until all are loaded, or stop() is called."""
        for count, game in enumerate(self.games, 1):
            if self.stopped.is_set():
                return
            try:
                game.load_titlescreen()
            except Exception:  # noqa: BLE001
                message = f"Failed to load {game.title}\n\n{traceback.format_exc()}"
                pg.event.post(pg.event.Event(LOADING_FAILED, message=message))
                return
            if count % BATCH_SIZE == 0 or count == len(self.games):
                pg.event.post(pg.event.Event(GAMES_LOADED))

    def stop(self) -> None:
        """Stop loading, and wait for the title screen being loaded."""
        self.stopped.set()
        self.join()


gamelist = Gamelist()
