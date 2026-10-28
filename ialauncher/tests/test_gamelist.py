"""The list of games."""

import unittest
from pathlib import Path

from ialauncher.game import Game
from ialauncher.gamelist import Gamelist


def game(name: str, *, autoplayable: bool) -> Game:
    """Return a game that is autoplayable, or not."""
    metadata = {"title": name, "year": "1990", "url": f"https://example.com/{name}"}
    game = Game(Path(name), metadata)
    game.autoplayable = autoplayable
    return game


class TestGamelist(unittest.TestCase):
    """The list of games."""

    def test_random_game(self) -> None:
        """A random game is always one that autoplays."""
        gamelist = Gamelist()
        gamelist.all_games[:] = [
            game("A", autoplayable=False),
            game("B", autoplayable=True),
            game("C", autoplayable=False),
        ]
        for _ in range(20):
            gamelist.random_game()
            self.assertEqual(gamelist.current_game, 1)

    def test_no_random_game(self) -> None:
        """Without games that autoplay, the current game stays."""
        gamelist = Gamelist()
        gamelist.all_games[:] = [
            game("A", autoplayable=False),
            game("B", autoplayable=False),
        ]
        gamelist.current_game = 1
        gamelist.random_game()
        self.assertEqual(gamelist.current_game, 1)
