"""Support for headless testing of IA Launcher."""

import copy
import functools
import os
import random
import sys
import tempfile
import unittest
from collections import defaultdict
from collections.abc import Callable, Generator
from inspect import GEN_CREATED, GEN_SUSPENDED, getgeneratorstate, isgeneratorfunction
from pathlib import Path
from unittest import mock

import pygame as pg

from ialauncher import __main__, bios, engine, options
from ialauncher.cga import cga
from ialauncher.cheats import cheats
from ialauncher.game import Game
from ialauncher.gamelist import Gamelist, gamelist

type Step = pg.event.Event | list[pg.event.Event] | None
type Script = Generator[Step, engine.Scene | None, None]

TICK = pg.event.custom_type()
MAX_FRAMES = 10_000  # 300 is typical

# The games by directory, loaded once for all tests
games: dict[Path, Game] = {}
add_game = Gamelist.add


def add_game_once(gamelist: Gamelist, game_dir: Path) -> None:
    """Add a copy of the game, so that only the first test loads it."""
    if game_dir not in games:
        add_game(gamelist, game_dir)
        games[game_dir] = copy.copy(gamelist.all_games[-1])
    else:
        gamelist.all_games.append(copy.copy(games[game_dir]))


def finish_sound() -> None:
    """Stop the speaker, and let the sound play out, but not forever.

    Without a sound device, like on a GitHub runner, there is none.
    """
    bios.speaker.stop()
    deadline = pg.time.get_ticks() + 1000
    while pg.mixer.get_init() and pg.mixer.get_busy():
        if pg.time.get_ticks() > deadline:
            break
        pg.time.wait(10)


def key(key: int, mod: int = pg.KMOD_NONE, unicode: str = "") -> list[pg.event.Event]:
    """Return the events of pressing and releasing a key."""
    return [
        pg.event.Event(pg.KEYDOWN, key=key, mod=mod, unicode=unicode),
        pg.event.Event(pg.KEYUP, key=key, mod=mod),
    ]


class Typing(list[pg.event.Event]):
    """The events of typing text, which are sent one keystroke per frame."""


def text(string: str) -> Typing:
    """Return the events of typing a string."""
    return Typing(
        event for char in string for event in key(ord(char.lower()), unicode=char)
    )


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
        for name in ("fullscreen", "slideshow"):
            value = getattr(options, name)
            self.enterContext(mock.patch.object(options, name, value))
        self.enterContext(mock.patch.object(sys, "argv", list(self.argv)))
        self.enterContext(mock.patch.object(Game, "get_emulator", return_value=[]))
        self.enterContext(mock.patch.object(Gamelist, "add", add_game_once))
        vars(gamelist).update(vars(Gamelist()))  # Start each test with no games
        for method in ("download", "start"):
            error = AssertionError(f"The app tried to {method} a game")
            self.enterContext(mock.patch.object(Game, method, side_effect=error))
        self.addCleanup(pg.quit)
        self.addCleanup(finish_sound)
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
        self.pressed: set[int] = set()  # The keys held down after the last step
        self.typing: list[pg.event.Event] = []  # The keystrokes still to type
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

            # Wait until the app has handled all events.
            if not pg.event.peek():
                self.post_step(script, scenes[-1])

        self.enterContext(mock.patch.object(engine.Scene, "run", run_scene))
        self.enterContext(mock.patch.object(pg.display, "flip", flip_display))
        self.enterContext(mock.patch.object(pg.key, "get_pressed", self.get_pressed))
        try:
            self.play(script)
        except Exception as e:
            if screen := pg.display.get_surface():
                fd, path = tempfile.mkstemp(prefix="ialauncher-", suffix=".png")
                os.close(fd)  # Windows can't open a file twice
                pg.image.save(screen, path)
                e.add_note(f"Screenshot of the last frame: {path}")
            raise

    def post(self, event: pg.event.Event) -> None:
        """Post the event, and keep track of the keys it holds down."""
        if event.type == pg.KEYDOWN:
            self.pressed.add(event.key)
        elif event.type == pg.KEYUP:
            self.pressed.discard(event.key)
        pg.event.post(event)

    def get_pressed(self) -> defaultdict[int, bool]:
        """Like the keyboard, report the keys held down after the last step."""
        return defaultdict(bool, dict.fromkeys(self.pressed, True))

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

    def post_step(self, script: Script, scene: engine.Scene) -> None:
        """Post the events of the next step, or the next keystroke of typing.

        The app handles one keystroke per frame, so typing posts one at a
        time, like a person, instead of all at once.
        """
        if not self.typing:
            events = self.next_events(script, scene)
            if not isinstance(events, Typing):
                for event in events:
                    self.post(event)
                return
            self.typing = list(events)
        for _ in range(2):  # Its KEYDOWN and KEYUP
            self.post(self.typing.pop(0))

    def next_events(self, script: Script, scene: engine.Scene) -> list[pg.event.Event]:
        """Send the scene to the script, and return the events of its next step."""
        started = getgeneratorstate(script) != GEN_CREATED
        try:
            step = script.send(scene if started else None)
        except StopIteration:
            self.fail("The script has finished, but the app is still running")
        return step if isinstance(step, list) else [step or pg.event.Event(TICK)]
