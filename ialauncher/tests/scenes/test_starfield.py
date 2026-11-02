"""Starfield and Stars: the screensaver."""

import pygame as pg

from ialauncher import options
from ialauncher.scenes import BLACK
from ialauncher.scenes.grid import Grid
from ialauncher.scenes.hero import Hero
from ialauncher.scenes.starfield import Starfield
from ialauncher.scenes.stars import Stars
from ialauncher.tests.support import HeadlessTestCase, Script, key, screen


class TestStarfield(HeadlessTestCase):
    """Starfield."""

    loaded = True

    def test_filling(self) -> Script:
        """The field starts with few stars nearby and more further away."""
        starfield = Starfield(Hero())
        yield starfield
        stars = starfield.stars
        self.assertLess(len(stars), options.density)
        self.assertGreater(len(stars), options.density // 4)
        near = sum(2 * star.z < 1 for star in stars)
        self.assertLess(near, len(stars) - near)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_far_to_near(self) -> Script:
        """Stars are drawn from far to near, also after adding a center star."""
        starfield = Starfield(Hero())
        yield starfield
        yield key(pg.K_SPACE)
        depths = [star.z for star in starfield.stars]
        self.assertEqual(depths, sorted(depths, reverse=True))
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

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


class TestStars(HeadlessTestCase):
    """Stars."""

    loaded = True

    def test_stars(self) -> Script:
        """The screen is black while stars.exe runs, and keys are ignored."""
        yield Stars(Hero())
        self.assertIsInstance((yield key(pg.K_ESCAPE)), Stars)
        self.assertEqual(screen().get_at((0, 0)), BLACK)
        self.assertEqual(self.stars_launched, 1)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_cant_start(self) -> Script:
        """Without DOSBox, return to the previous scene right away."""
        self.stars_start = False
        grid = Grid()
        self.assertIs((yield Stars(grid)), grid)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
