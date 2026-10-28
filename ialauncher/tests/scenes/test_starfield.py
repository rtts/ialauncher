"""Starfield and Stars: the screensaver."""

import pygame as pg

from ialauncher.scenes import BLACK
from ialauncher.scenes.hero import Hero
from ialauncher.scenes.starfield import Starfield
from ialauncher.scenes.stars import Stars
from ialauncher.tests.support import HeadlessTestCase, Script, key, screen


class TestStarfield(HeadlessTestCase):
    """Starfield."""

    loaded = True

    def test_space(self) -> Script:
        """Space adds a star in the exact center."""
        starfield = Starfield(Hero())
        yield starfield
        centered = sum(star.x == star.y == 0 for star in starfield.stars)
        yield key(pg.K_SPACE)
        self.assertEqual(
            sum(star.x == star.y == 0 for star in starfield.stars), centered + 1
        )
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_enter(self) -> Script:
        """Enter starts stars.exe alongside the starfield."""
        yield Starfield(Hero())
        self.assertIsInstance((yield key(pg.K_RETURN)), Starfield)
        self.assertEqual(self.stars_launched, 1)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))


class TestStars(HeadlessTestCase):
    """Stars."""

    loaded = True

    def test_stars(self) -> Script:
        """The screen is black while stars.exe runs."""
        yield Stars(Hero())
        self.assertIsInstance((yield key(pg.K_ESCAPE)), Stars)
        self.assertEqual(screen().get_at((0, 0)), BLACK)
        self.assertEqual(self.stars_launched, 1)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
