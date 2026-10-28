"""The engine: the outer loop over scenes, and the inner loop of each scene."""

from typing import override
from unittest import mock

import pygame as pg

from ialauncher import engine

from .support import End, HeadlessTestCase, Script, key


class Probe(engine.Scene):
    """A scene that logs its hooks and events, and returns what it's told to."""

    def __init__(
        self,
        log: list[str],
        *,
        start: engine.NextScene = None,
        update: engine.NextScene = None,
        post: pg.event.Event | None = None,
    ) -> None:
        """Prepare to return the given scenes from start() and update()."""
        super().__init__()
        self.log = log
        self.next_from_start = start
        self.next_from_update = update
        self.post = post

    @override
    def update(self) -> engine.NextScene:
        """Log the frame, post the event, if any, and return the next scene."""
        self.log.append("update")
        if self.post:
            pg.event.post(self.post)
        return self.next_from_update

    @override
    def handle(self, event: pg.event.Event) -> engine.NextScene:
        """Log the key."""
        if event.type == pg.KEYDOWN:
            self.log.append(pg.key.name(event.key))
        return None

    @override
    def intercept(self, event: pg.event.Event) -> bool:
        """Intercept the X key."""
        return event.type == pg.KEYDOWN and event.key == pg.K_x

    @override
    def start(self) -> engine.NextScene:
        """Log the start, and return the next scene, if any."""
        self.log.append("start")
        return self.next_from_start

    @override
    def stop(self) -> None:
        """Log the stop."""
        self.log.append("stop")


class TestEngine(HeadlessTestCase):
    """The engine."""

    def test_start_skips(self) -> Script:
        """A scene that returns the next scene from start() never runs or stops."""
        log: list[str] = []
        yield Probe(log, start=End())
        yield from self.wait_until_quit()
        self.assertEqual(log, ["start"])
        self.assertEqual(self.trace, ["Probe", "End"])

    def test_stop_after_last_frame(self) -> Script:
        """A scene stops after the frame that returns the next scene."""
        log: list[str] = []
        yield Probe(log, update=End())
        yield from self.wait_until_quit()
        self.assertEqual(log, ["start", "update", "stop"])
        self.assertEqual(self.trace, ["Probe", "End"])

    def test_stop_on_quit(self) -> Script:
        """A scene stops when the window closes."""
        log: list[str] = []
        yield Probe(log)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
        self.assertEqual(log[-1], "stop")

    def test_false_quits(self) -> Script:
        """Returning False instead of the next scene quits."""
        log: list[str] = []
        yield Probe(log, update=False)
        yield from self.wait_until_quit()
        self.assertEqual(self.trace, ["Probe"])

    def test_quit_keys(self) -> Script:
        """Ctrl-Q quits from any scene."""
        log: list[str] = []
        yield Probe(log)
        self.assertIsNone((yield key(pg.K_q, pg.KMOD_LCTRL)))
        self.assertNotIn("q", log)

    def test_close_keys(self) -> Script:
        """Ctrl-W quits from any scene."""
        yield Probe([])
        self.assertIsNone((yield key(pg.K_w, pg.KMOD_LCTRL)))

    def test_exit_keys(self) -> Script:
        """Alt-X quits from any scene."""
        yield Probe([])
        self.assertIsNone((yield key(pg.K_x, pg.KMOD_LALT)))

    def test_pending_quit(self) -> Script:
        """A quit that's pending when a scene returns the next one stops the engine."""
        self.assertIsNone((yield Probe([], update=End(), post=pg.event.Event(pg.QUIT))))
        self.assertEqual(self.trace, ["Probe"])

    def test_events(self) -> Script:
        """Events reach handle() after the frame, unless intercepted."""
        log: list[str] = []
        yield Probe(log)
        yield [*key(pg.K_a), *key(pg.K_x), *key(pg.K_b)]
        self.assertEqual(log, ["start", "update", "a", "b", "update"])
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))

    def test_fullscreen(self) -> Script:
        """F11 switches between fullscreen and a window."""
        set_mode = self.enterContext(
            mock.patch.object(engine, "set_mode", wraps=engine.set_mode)
        )
        yield Probe([])
        yield key(pg.K_F11)
        set_mode.assert_called_with(fullscreen=True)
        self.assertIsNone((yield pg.event.Event(pg.QUIT)))
