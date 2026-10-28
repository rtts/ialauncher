"""A _very_ simple engine for building pygame games.

There is a function, run(), and a class, Scene, which is meant to
be subclassed by your own custom scenes. Example usage:

    class Intro(Scene):
        def __init__(self):
            self.image = pg.image.load("my_awesome_title_screen.png")
            super().__init__()

        @override
        def handle(self, event):
            if event.type == pg.KEYDOWN:
                return LevelOne()

        @override
        def update(self):
            self.screen.blit(self.image, (0, 0))

    if __name__ == "__main__":
        scene = Intro()
        run(scene, title="My awesome game")
"""

from abc import ABC, abstractmethod
from typing import Literal, final

import pygame as pg

from ialauncher.bios import held_keys, kb_int

type NextScene = Scene | Literal[False] | None

QUIT_KEYS = {(pg.K_q, pg.KMOD_CTRL), (pg.K_w, pg.KMOD_CTRL), (pg.K_x, pg.KMOD_ALT)}
window_size = [640, 480]


def run(scene: NextScene, title: str = "Game", *, fullscreen: bool = True) -> None:
    """Initialize pygame and run scene loop starting with scene."""
    pg.mixer.pre_init(44100, -16, 1, allowedchanges=0)
    pg.init()
    pg.key.set_repeat(250, 50)
    pg.event.set_blocked(pg.TEXTINPUT)
    pg.display.set_caption(title)
    screen = set_mode(fullscreen=fullscreen)
    while scene:
        pg.event.clear()
        held_keys.clear()
        scene = scene._run(screen)  # noqa: SLF001 - the only caller
        if pg.event.peek(pg.QUIT):  # Also when it quit and returned a scene
            break


def set_mode(*, fullscreen: bool) -> pg.Surface:
    """Set display mode to windowed or fullscreen."""
    if fullscreen:
        if pg.display.get_surface() and not pg.display.is_fullscreen():
            window_size[:] = pg.display.get_window_size()
        return pg.display.set_mode(flags=pg.FULLSCREEN)
    return pg.display.set_mode(window_size, flags=pg.RESIZABLE)


class Scene(ABC):
    """Base class for scenes.

    Subclasses must implement the update() and handle() methods.
    """

    screen: pg.Surface

    def __init__(self) -> None:
        """Create the clock that caps the frame rate."""
        self.clock = pg.time.Clock()

    @abstractmethod
    def update(self) -> NextScene:
        """Draw a frame and return the next scene, False to quit, or None."""

    @abstractmethod
    def handle(self, event: pg.event.Event) -> NextScene:
        """Handle an event and return the next scene, False to quit, or None."""

    def start(self) -> NextScene:
        """Get ready before the first frame."""
        return None

    def stop(self) -> None:
        """Clean up after the last frame."""
        return

    @property
    def show_mouse(self) -> bool:
        """Whether the mouse pointer is visible."""
        return False

    def intercept(self, event: pg.event.Event) -> bool:  # noqa: ARG002
        """Return True to intercept an event before it reaches handle()."""
        return False

    def get_events(self) -> list[pg.event.Event]:
        """Cap inner game loop at 60fps."""
        self.clock.tick(60)
        return pg.event.get()

    @final
    def _run(self, screen: pg.Surface) -> NextScene:
        """Run this scene's game loop.

        DO NOT OVERRIDE!
        """
        self.screen = screen
        if (next_scene := self.start()) is not None:
            return next_scene
        try:
            while True:
                pg.mouse.set_visible(self.show_mouse)
                next_scene = self.update()
                pg.display.flip()
                if next_scene is not None:
                    return next_scene
                for event in self.get_events():
                    if not kb_int(event):
                        continue
                    if event.type == pg.QUIT or (
                        event.type == pg.KEYDOWN
                        and any(event.key == k and event.mod & m for k, m in QUIT_KEYS)
                    ):
                        pg.event.post(pg.event.Event(pg.QUIT))
                        return None
                    if event.type == pg.KEYDOWN and event.key == pg.K_F11:
                        set_mode(fullscreen=not pg.display.is_fullscreen())
                    elif not self.intercept(event):
                        next_scene = self.handle(event)
                        if next_scene is not None:
                            return next_scene
        finally:
            self.stop()
