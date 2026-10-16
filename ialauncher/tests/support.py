"""Helpers for testing IA Launcher.

Tests subclass HeadlessTestCase, and each test method that is a generator
is a script that drives the app: it yields the events to post (or None
to just wait a frame), and is sent the scene that is running once the
app has handled them. After the app quits, the script is sent None and
should then return. If the app raises an exception instead, it is
raised in the script, at the step that caused it.
"""

import functools
import random
import sys
import tempfile
import unittest
from collections.abc import Callable, Generator
from inspect import GEN_CREATED, GEN_SUSPENDED, getgeneratorstate, isgeneratorfunction
from unittest import mock

import pygame as pg

from ialauncher import __main__, engine, options
from ialauncher.cga import cga
from ialauncher.cheats import cheats
from ialauncher.game import Game

type Step = pg.event.Event | list[pg.event.Event] | None
type Script = Generator[Step, engine.Scene | None, None]

# Posted to wake up scenes that sleep until the next event
TICK = pg.event.custom_type()

# Give up when the app runs this many frames (loading takes about 300)
MAX_FRAMES = 10_000


def key(key: int, mod: int = pg.KMOD_NONE, unicode: str = "") -> list[pg.event.Event]:
    """Return the events of pressing and releasing a key."""
    return [
        pg.event.Event(pg.KEYDOWN, key=key, mod=mod, unicode=unicode),
        pg.event.Event(pg.KEYUP, key=key, mod=mod),
    ]


def text(string: str) -> list[pg.event.Event]:
    """Return the events of typing a string."""
    return [event for char in string for event in key(ord(char.lower()), unicode=char)]


def scripted(
    test: Callable[["HeadlessTestCase"], Script],
) -> Callable[["HeadlessTestCase"], None]:
    """Turn a test method that is a script into one that runs the app."""

    @functools.wraps(test)
    def run(self: HeadlessTestCase) -> None:
        self.run_app(test(self))

    return run


class HeadlessTestCase(unittest.TestCase):
    """Run IA Launcher headless, without downloading or starting games."""

    argv = ("ialauncher", "--no-fullscreen", "--slideshow", "0")

    def __init_subclass__(cls) -> None:
        """Run the test methods that are generators as scripts."""
        super().__init_subclass__()
        for name, method in list(vars(cls).items()):
            if name.startswith("test") and isgeneratorfunction(method):
                setattr(cls, name, scripted(method))

    def setUp(self) -> None:
        """Reset the global state, and restore it after the test."""
        for name in ("fullscreen", "slideshow", "captures_dir"):
            value = getattr(options, name)
            self.enterContext(mock.patch.object(options, name, value))
        self.enterContext(mock.patch.object(sys, "argv", list(self.argv)))
        for method in ("download", "start"):
            error = AssertionError(f"The app tried to {method} a game")
            self.enterContext(mock.patch.object(Game, method, side_effect=error))
        self.addCleanup(pg.quit)
        self.addCleanup(cga.set_palette, None)
        cheats.typed = ""
        random.seed(0)

    def wait_for[T: engine.Scene](
        self, scene_type: type[T]
    ) -> Generator[Step, engine.Scene | None, T]:
        """Wait until a scene of the given type is running, and return it."""
        while not isinstance(scene := (yield None), scene_type):
            if scene is None:
                self.fail(f"The app quit before {scene_type.__name__} started")
        return scene

    def run_app(self, script: Script) -> None:
        """Run the app, and feed it the steps of the script, one frame at a time.

        If the test fails, the last frame is saved as a screenshot.
        """
        scenes: list[engine.Scene] = []  # The running scenes, innermost last
        frames = 0
        run, flip = engine.Scene.run, pg.display.flip

        def run_scene(scene: engine.Scene, screen: pg.Surface) -> engine.NextScene:
            scenes.append(scene)
            try:
                return run(scene, screen)
            finally:
                scenes.pop()

        def flip_display() -> None:
            nonlocal frames
            flip()
            frames += 1
            if frames > MAX_FRAMES:
                self.fail(f"The app is still running after {MAX_FRAMES} frames")
            if not pg.event.peek():  # Wait until the app has handled all events
                for event in self.next_events(script, scenes[-1]):
                    pg.event.post(event)

        self.enterContext(mock.patch.object(engine.Scene, "run", run_scene))
        self.enterContext(mock.patch.object(pg.display, "flip", flip_display))
        try:
            self.play(script)
        except Exception as e:
            if screen := pg.display.get_surface():
                path = tempfile.mkstemp(prefix="ialauncher-", suffix=".png")[1]
                pg.image.save(screen, path)
                e.add_note(f"Screenshot of the last frame: {path}")
            raise

    def play(self, script: Script) -> None:
        """Run the app, then tell the script how it ended."""
        try:
            try:
                __main__.main()
            except Exception as e:
                if getgeneratorstate(script) != GEN_SUSPENDED:
                    raise
                script.throw(e)  # Raise it at the step that caused it
            else:
                script.send(None)
            self.fail("The app quit before the script finished")
        except StopIteration:
            pass

    def next_events(self, script: Script, scene: engine.Scene) -> list[pg.event.Event]:
        """Send the scene to the script, and return the events of its next step."""
        started = getgeneratorstate(script) != GEN_CREATED
        try:
            step = script.send(scene if started else None)
        except StopIteration:
            self.fail("The script has finished, but the app is still running")
        return step if isinstance(step, list) else [step or pg.event.Event(TICK)]
