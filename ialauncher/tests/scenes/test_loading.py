"""Loading: loading all games behind a progress bar."""

import pygame as pg

from ialauncher.gamelist import gamelist
from ialauncher.scenes.hero import Hero
from ialauncher.scenes.loading import Loading
from ialauncher.tests.support import GAMES_DIR, HeadlessTestCase, Script, find_games


class TestLoading(HeadlessTestCase):
    """Loading."""

    def test_loading(self) -> Script:
        """All games are loaded in alphabetical order, starting with a random one."""
        yield Loading()
        yield from self.wait_for(Hero)
        names = [game.identifier for game in gamelist.all_games]
        self.assertEqual(sorted(names), sorted(find_games(GAMES_DIR)))
        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_main(self) -> Script:
        """The app starts with Loading."""
        yield None
        yield from self.wait_for(Hero)
        self.assertEqual(self.trace, ["Loading", "Hero"])
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_slurp(self) -> Script:
        """Slurping downloads every game, and then quits."""
        loading = Loading(slurp=True)
        del loading.todo[3:]
        loading.total = 3
        yield loading
        yield from self.wait_until_quit()
        self.assertEqual(len(self.downloads), 3)
        self.assertEqual(set(self.files.values()), {"downloaded"})
