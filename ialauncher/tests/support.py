"""Support for headless testing of IA Launcher."""

import copy
import functools
import os
import random
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict
from collections.abc import Callable, Generator
from inspect import GEN_SUSPENDED, getgeneratorstate, isgeneratorfunction
from pathlib import Path
from typing import Any, ClassVar, override
from unittest import mock

import pygame as pg

import games as gd
from ialauncher import __main__, bios, engine, options, scenes, utils
from ialauncher.cga import cga
from ialauncher.cheats import cheats
from ialauncher.game import EMULATOR_FAILED, Download, Emulator, Game, Unzip
from ialauncher.gamelist import Gamelist, gamelist
from ialauncher.scenes import browse, crt, download, loading, play, stars, unzip

type Events = pg.event.Event | list[pg.event.Event] | None
type Step = Events | engine.Scene
type Script = Generator[Step, engine.Scene | None, None]

TICK = pg.event.custom_type()
MAX_FRAMES = 10_000
GAMES_PER_FRAME = 1000
GAMES_DIR = Path(gd.__file__).parent

games: dict[Path, Game] = {}
add_game = Gamelist.add
load_games = loading.Loading.load_games
start_crt = crt.CRT.start


@functools.cache
def find_games(games_dir: Path) -> dict[str, dict[str, str] | None]:
    """Find the games once, like a metadata cache without the metadata."""
    return {
        entry.name: None
        for entry in games_dir.iterdir()
        if (entry / "metadata.ini").exists()
    }


def add_game_once(
    gamelist: Gamelist, game_dir: Path, metadata: dict[str, str] | None = None
) -> None:
    """Add a copy of the game, so that only the first test loads it."""
    if game_dir not in games:
        add_game(gamelist, game_dir, metadata)
        games[game_dir] = copy.copy(gamelist.all_games[-1])
    else:
        gamelist.all_games.append(copy.copy(games[game_dir]))


def load_many_games(scene: loading.Loading, _: int) -> None:
    """Load GAMES_PER_FRAME games, however many the scene asks for."""
    load_games(scene, GAMES_PER_FRAME)


class Clock:
    """A clock that doesn't cap the frame rate, so that tests run full speed."""

    def tick(self, _: int = 0) -> int:
        """Return immediately."""
        return 0


class End(scenes.Scene):
    """The scene after the scene under test, which quits."""

    @override
    def update(self) -> engine.NextScene:
        """Quit."""
        return False

    @override
    def handle(self, event: pg.event.Event) -> engine.NextScene:
        """Ignore everything."""
        return None


class Paint(scenes.Scene):
    """A scene that paints the screen in one color, and continues."""

    def __init__(self, color: tuple[int, int, int], then: engine.Scene) -> None:
        """Prepare to paint the screen."""
        super().__init__()
        self.color = color
        self.then = then

    @override
    def update(self) -> engine.NextScene:
        """Paint the screen, and continue."""
        self.draw()
        return self.then

    @override
    def handle(self, event: pg.event.Event) -> engine.NextScene:
        """Ignore everything."""
        return None

    @override
    def draw(self) -> None:
        """Paint the screen."""
        self.screen.fill(self.color)


class Faked:
    """A thread that never runs, but that the test finishes instead."""

    alive = True
    error: str | None
    effect: Callable[[], None]

    def is_alive(self) -> bool:
        """Return whether the test hasn't finished it yet."""
        return self.alive

    def finish(self, error: str | None = None) -> None:
        """Finish, with its effect unless there's an error."""
        self.alive = False
        self.error = error
        if error is None:
            self.effect()


class FakeDownload(Faked, Download):
    """A download that the test finishes."""

    def __init__(self, game: Game, effect: Callable[[], None]) -> None:
        """Prepare to download the game."""
        super().__init__(game.urls, game.gamedir)
        self.effect = effect

    @override
    def cancel(self) -> None:
        """Cancel the download."""
        self.cancelled.set()
        self.alive = False


class FakeUnzip(Faked, Unzip):
    """An unzip that the test finishes."""

    def __init__(self, game: Game, effect: Callable[[], None]) -> None:
        """Prepare to unzip the game."""
        super().__init__(game.urls, game.gamedir, extract=False)
        self.effect = effect


class FakeEmulator(Emulator):
    """An emulator that runs until the test makes it exit."""

    def __init__(self, game: Game, *, running: bool) -> None:
        """Start running, or not."""
        super().__init__(game, [])
        self.running = running

    @override
    def is_alive(self) -> bool:
        """Return whether it's running."""
        return self.running

    @override
    def stop(self) -> None:
        """Stop running."""
        self.stopped = True
        self.running = False

    def exit(self, error: str | None = None) -> None:
        """Exit, after reporting the error, if any."""
        if error:
            pg.event.post(pg.event.Event(EMULATOR_FAILED, message=error))
        self.running = False


def stop_timers() -> None:
    """Stop the timers of all custom events, which pg.quit() would do too."""
    if not pg.get_init():
        return
    for event_type in range(pg.USEREVENT, pg.event.custom_type()):
        pg.time.set_timer(event_type, 0)


def finish_sound() -> None:
    """Stop the speaker, and let the sound play out, but not forever."""
    bios.speaker.stop()
    deadline = pg.time.get_ticks() + 1000
    while pg.mixer.get_init() and pg.mixer.get_busy():
        if pg.time.get_ticks() > deadline:
            break
        pg.time.wait(10)


def screen() -> pg.Surface:
    """Return the screen, which exists while the app runs."""
    surface = pg.display.get_surface()
    if surface is None:
        msg = "There is no screen"
        raise RuntimeError(msg)
    return surface


def scene_names() -> set[str]:
    """Return the names of all scene classes."""
    names: set[str] = set()
    classes: list[type[engine.Scene]] = [engine.Scene]
    while classes:
        cls = classes.pop()
        names.add(cls.__name__)
        classes.extend(cls.__subclasses__())
    return names


def key(key: int, mod: int = pg.KMOD_NONE, unicode: str = "") -> list[pg.event.Event]:
    """Return the events of pressing and releasing a key."""
    return [
        pg.event.Event(pg.KEYDOWN, key=key, mod=mod, unicode=unicode),
        pg.event.Event(pg.KEYUP, key=key, mod=mod),
    ]


def click(pos: tuple[int, int], button: int = pg.BUTTON_LEFT) -> pg.event.Event:
    """Return the event of clicking at the position."""
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=button)


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
    """Run IA Launcher headless, with fake downloads, unzips and emulators.

    A test that is a generator is a script. It starts the app with
    __main__, or with the scene of its first step, and then sends the
    events of each step after a frame, to which the app sends back the
    scene that drew it, or None once the app has quit.
    """

    argv = ("ialauncher", "--no-fullscreen", "--slideshow", "0")
    loaded: ClassVar[bool] = False

    def __init_subclass__(cls) -> None:
        """Run the test methods that are generators as scripts."""
        super().__init_subclass__()
        for name, method in list(vars(cls).items()):
            if name.startswith("test") and isgeneratorfunction(method):
                setattr(cls, name, scripted(method))

    def setUp(self) -> None:
        """Reset the global state, fake the outside world, and load the games."""
        for name in ("fullscreen", "slideshow", "autoplay", "idle"):
            value = getattr(options, name)
            self.enterContext(mock.patch.object(options, name, value))
        self.enterContext(mock.patch.object(sys, "argv", list(self.argv)))
        self.enterContext(mock.patch.object(Gamelist, "add", add_game_once))
        self.enterContext(mock.patch.object(pg.time, "Clock", Clock))
        self.enterContext(mock.patch.object(loading, "read_metadata_cache", find_games))
        self.enterContext(
            mock.patch.object(loading.Loading, "load_games", load_many_games)
        )
        vars(gamelist).update(vars(Gamelist()))
        self.trace: list[str] = []
        self.errors: list[str] = []
        self.animate_crt = False
        self.fake_crt()
        self.fake_errors()
        self.fake_games()
        self.fake_stars()
        self.addCleanup(stop_timers)
        self.addCleanup(finish_sound)
        self.addCleanup(cga.set_palette, None)
        cheats.typed = ""
        random.seed(0)
        if self.loaded:
            self.load()

    def fake_crt(self) -> None:
        """Skip the frames of CRT, unless the test animates it."""

        def start(scene: crt.CRT) -> engine.NextScene:
            return start_crt(scene) if self.animate_crt else scene.then

        self.enterContext(mock.patch.object(crt.CRT, "start", start))

    def fake_errors(self) -> None:
        """Collect the errors instead of showing them."""
        for module in (utils, scenes, browse, download, unzip, play, loading):
            self.enterContext(
                mock.patch.object(module, "show_error", self.errors.append)
            )

    def fake_games(self) -> None:
        """Fake the files, downloads, unzips and emulators of all games."""
        self.files: dict[str, str] = {}
        self.downloads: list[FakeDownload] = []
        self.unzips: list[FakeUnzip] = []
        self.emulators: list[FakeEmulator] = []
        self.changed: list[Game] = []
        self.finish_jobs = True
        self.keep_running = False
        files = self.files

        def becomes(game: Game, state: str) -> Callable[[], None]:
            return lambda: files.update({game.identifier: state})

        def is_downloaded(game: Game) -> bool:
            return files.get(game.identifier) in {"downloaded", "ready"}

        def is_ready(game: Game) -> bool:
            return files.get(game.identifier) == "ready"

        def reset(game: Game) -> None:
            files.pop(game.identifier, None)

        def start_download(game: Game) -> None:
            game.download_thread = self.job(
                self.downloads, FakeDownload(game, becomes(game, "downloaded"))
            )

        def start_unzip(game: Game) -> Unzip:
            if game.unzip_thread and game.unzip_thread.is_alive():
                return game.unzip_thread
            game.unzip_thread = self.job(
                self.unzips, FakeUnzip(game, becomes(game, "ready"))
            )
            return game.unzip_thread

        for name, fake in (
            ("is_downloaded", is_downloaded),
            ("is_ready", is_ready),
            ("reset", reset),
            ("download", start_download),
            ("unzip", start_unzip),
        ):
            self.enterContext(mock.patch.object(Game, name, fake))
        self.fake_emulators()

    def fake_emulators(self) -> None:
        """Fake the emulators, and the metadata.ini files that change."""

        def start(game: Game, **_: object) -> Emulator:
            emulator = FakeEmulator(game, running=self.keep_running)
            self.emulators.append(emulator)
            return emulator

        def changed_games(_: Gamelist) -> list[Game]:
            changed = list(self.changed)
            self.changed.clear()
            return changed

        self.enterContext(mock.patch.object(Game, "start", start))
        self.enterContext(mock.patch.object(Game, "get_emulator", lambda _: []))
        self.enterContext(mock.patch.object(Game, "reload_metadata", lambda _: True))
        self.enterContext(mock.patch.object(Gamelist, "changed_games", changed_games))
        self.enterContext(mock.patch.object(play, "get_dosbox_command"))

    def fake_stars(self) -> None:
        """Fake stars.exe, which starts unless the test says it can't."""
        self.stars_start = True
        self.stars_launched = 0
        self.enterContext(mock.patch.object(stars.Stars, "dosbox", None))

        def launch(**_: object) -> bool:
            if not self.stars_start:
                return False
            self.stars_launched += 1
            process: Any = mock.create_autospec(subprocess.Popen, instance=True)
            process.poll.return_value = None
            stars.Stars.dosbox = process
            return True

        self.enterContext(mock.patch.object(stars.Stars, "launch", launch))

    def job[T: FakeDownload | FakeUnzip](self, jobs: list[T], job: T) -> T:
        """Keep track of the job, and finish it right away, unless told not to."""
        jobs.append(job)
        if self.finish_jobs:
            job.finish()
        return job

    def load(self) -> None:
        """Load all games, like Loading does, but at once."""
        for name in find_games(GAMES_DIR):
            gamelist.add(GAMES_DIR / name)
        gamelist.sort()
        gamelist.random_game()

    def game(self, state: str | None = None) -> Game:
        """Return the first game, with its files in the given state, if any."""
        game = gamelist.games[0]
        if state:
            self.files[game.identifier] = state
        return game

    def qualify(self, game: Game | None, state: str = "downloaded") -> Game:
        """Make the game qualify to autoplay, and return it."""
        if game is None:
            self.fail("No game to autoplay")
        options.autoplay = 300
        game.engine = "dosbox"
        game.emulator_start = "GAME.EXE"
        game.autoplayable = True
        self.files[game.identifier] = state
        return game

    def change_metadata(self, _: engine.Scene) -> Events:
        """Change the metadata.ini of the current game."""
        if game := gamelist.get_current_game():
            self.changed.append(game)
        return None

    def exit_stars(self) -> None:
        """Make stars.exe exit."""
        process: Any = stars.Stars.dosbox
        process.poll.return_value = 0

    def wait_for[T: engine.Scene](
        self, scene_type: type[T]
    ) -> Generator[Step, engine.Scene | None, T]:
        """Wait until a scene of the given type is running, and return it."""
        while not isinstance(scene := (yield None), scene_type):
            if scene is None:
                self.fail(f"The app quit before {scene_type.__name__} started")
        return scene

    def wait_until_quit(self) -> Generator[Step, engine.Scene | None, None]:
        """Wait until the app has quit."""
        while (yield None) is not None:
            pass

    def expect[T: engine.Scene](
        self,
        start: T,
        trigger: Events | Callable[[T], Events] = None,
        react: dict[type[engine.Scene], Events | Callable[[Any], Events]] | None = None,
    ) -> Script:
        """Start with the scene, trigger the transition, and check the scenes after.

        The transition is the test's docstring, like Hero > minus > Grid,
        or Loading > Hero without a trigger, where A/B means either, and
        Any any scene. The trigger is the part after the first scene, if
        that isn't a scene. The react steps, or what they return, are sent
        once to the scenes of their type along the way.
        """
        line = (self.shortDescription() or "").removesuffix(".")
        first, *rest = (part.strip() for part in line.split(">"))
        names = scene_names() | {"quit"}
        if rest and not set(rest[0].split("/")) <= names:
            causes, expected = rest[:1], rest[1:]
        else:
            causes, expected = [], rest
        if not causes and trigger is not None:
            self.fail(f"{line} has no trigger")
        scene = yield start
        if trigger is None or isinstance(trigger, pg.event.Event | list):
            scene = yield trigger
        else:
            scene = yield trigger(start)
        reacted: set[type[engine.Scene]] = set()
        while scene is not None and len(self.trace) <= len(expected):
            step = None
            for kind, events in (react or {}).items():
                if isinstance(scene, kind) and kind not in reacted:
                    reacted.add(kind)
                    if events is None or isinstance(events, pg.event.Event | list):
                        step = events
                    else:
                        step = events(scene)
            scene = yield step
        observed = [*self.trace[1:], *(["quit"] if scene is None else [])]
        matches = (
            first in ("Any", *self.trace[:1])
            and len(observed) == len(expected)
            and all(
                name in alternatives.split("/")
                for name, alternatives in zip(observed, expected, strict=True)
            )
        )
        actual = " > ".join([*self.trace[:1], *causes, *observed])
        self.assertTrue(matches, f"{actual} instead of {line}")
        if scene is not None:
            self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def run_app(self, script: Script) -> None:
        """Run the app and the script.

        If the test fails, the last frame is saved as a screenshot.
        """
        scenes: list[engine.Scene] = []
        self.pressed: set[int] = set()
        self.typing: list[pg.event.Event] = []
        frames = 0
        run, flip = engine.Scene._run, pg.display.flip  # noqa: SLF001

        def run_scene(scene: engine.Scene, screen: pg.Surface) -> engine.NextScene:
            self.trace.append(type(scene).__name__)
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
            if not pg.event.peek():
                self.post_step(script, scenes[-1])

        with (
            mock.patch.object(engine.Scene, "_run", run_scene),
            mock.patch.object(pg.display, "flip", flip_display),
            mock.patch.object(pg.key, "get_pressed", self.get_pressed),
        ):
            try:
                self.play(script)
            except Exception as e:
                if screen := pg.display.get_surface():
                    fd, path = tempfile.mkstemp(prefix="ialauncher-", suffix=".png")
                    os.close(fd)
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
        """Run the app from the script's first step, then tell it how it ended."""
        try:
            try:
                first = next(script)
                if isinstance(first, engine.Scene):
                    engine.run(first, fullscreen=False)
                elif first is None:
                    __main__.main()
                else:
                    self.fail("The first step is a scene, or None")
            except Exception as e:
                if getgeneratorstate(script) != GEN_SUSPENDED:
                    raise
                script.throw(e)
            else:
                script.send(None)
            self.fail("The app quit before the script finished")
        except StopIteration:
            pass
        finally:
            gamelist.stop_loading()
            gamelist.stop_watching()

    def post_step(self, script: Script, scene: engine.Scene) -> None:
        """Post the events of the next step, or the next keystroke of typing."""
        if not self.typing:
            events = self.next_events(script, scene)
            if not isinstance(events, Typing):
                for event in events:
                    self.post(event)
                return
            self.typing = list(events)
        for _ in range(2):
            self.post(self.typing.pop(0))

    def next_events(self, script: Script, scene: engine.Scene) -> list[pg.event.Event]:
        """Send the scene to the script, and return the events of its next step."""
        try:
            step = script.send(scene)
        except StopIteration:
            self.fail("The script has finished, but the app is still running")
        if isinstance(step, engine.Scene):
            self.fail("Only the first step can be a scene")
        return step if isinstance(step, list) else [step or pg.event.Event(TICK)]
