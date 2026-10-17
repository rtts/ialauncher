"""A list of all games without a title screen."""

import shutil
from pathlib import Path
from typing import override

import pygame as pg

from ialauncher import options
from ialauncher.engine import NextScene
from ialauncher.game import Game
from ialauncher.gamelist import GameList

from . import ANTIALIAS, Scene
from .download import Download


class Capture(Scene):
    """A list of all games without a title screen.

    While a game is running, watch the capture directory and move
    every new screenshot to the title.png of that game.
    """

    POLL_INTERVAL = 500

    def __init__(self, games: GameList) -> None:
        """List the games without a title screen."""
        self.games = [game for game in games.games if not game.get_titlescreen()]
        self.current = 0
        self.offset = 0
        self.captured: set[Game] = set()
        self.running: Game | None = None
        self.existing: set[str] = set()
        self.sizes: dict[str, int] = {}
        self.captures_dir = Path(options.captures_dir).expanduser()
        self.last_poll = 0
        self.preview: pg.Surface | None = None
        super().__init__()

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Move through the list, and play the selected game on Enter."""
        if event.type != pg.KEYDOWN:
            return None
        if event.key == pg.K_ESCAPE:
            return False
        moves = {
            pg.K_DOWN: 1,
            pg.K_UP: -1,
            pg.K_PAGEDOWN: 20,
            pg.K_PAGEUP: -20,
            pg.K_END: len(self.games),
            pg.K_HOME: -len(self.games),
        }
        if event.key in moves and self.games:
            self.current = max(
                0, min(len(self.games) - 1, self.current + moves[event.key])
            )
            self.preview = None
        if event.key == pg.K_RETURN and self.games and not self.running:
            game = self.games[self.current]
            if event.mod & pg.KMOD_SHIFT:
                game.reset()
            if not game.is_ready():
                Download(game).run(self.screen)
            if game.is_ready():
                self.watch(game)

                # Start playing (spawns a new thread)
                game.start(autorun=not event.mod & pg.KMOD_ALT)
        return None

    def watch(self, game: Game) -> None:
        """Remember the existing screenshots before the game starts."""
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.running = game
        self.existing = {path.name for path in self.captures_dir.iterdir()}
        self.sizes = {}

    def poll(self, game: Game) -> None:
        """Move new screenshots to the title screen of the given game.

        A screenshot is only moved once its size has stopped changing.
        """
        for path in sorted(self.captures_dir.iterdir()):
            name = path.name
            if name in self.existing or not name.lower().endswith(".png"):
                continue
            size = path.stat().st_size
            if size and self.sizes.get(name) == size:
                shutil.copyfile(path, game.path / "title.png")
                path.unlink()
                print(f"Captured {name} as title screen of {game.identifier}")
                self.captured.add(game)
                self.preview = None
                del self.sizes[name]
            else:
                self.sizes[name] = size

    @override
    def update(self, screen: pg.Surface) -> None:
        """Poll for screenshots, and draw the list and a preview."""
        if self.running and pg.time.get_ticks() - self.last_poll >= self.POLL_INTERVAL:
            self.last_poll = pg.time.get_ticks()
            running = self.running.is_running()
            self.poll(self.running)
            if not running:
                self.running = None

        screen.fill((0, 0, 0))
        if not hasattr(self, "font"):
            self.font = pg.font.SysFont("monospace", 24)
        rect = screen.get_rect()
        margin = 15
        line_height = self.font.get_linesize()

        status = (
            f"Running: {self.running.identifier}"
            if self.running
            else "Enter: play, Alt-Enter: play without autorun, Esc: quit"
        )
        header = f"{len(self.captured)} of {len(self.games)} captured | {status}"
        screen.blit(
            self.font.render(header, ANTIALIAS, (255, 255, 0)), (margin, margin)
        )

        # Game list on the left half, scrolled to keep the selection visible
        top = margin + 2 * line_height
        rows = max(1, (rect.height - top - margin) // line_height)
        if self.current < self.offset:
            self.offset = self.current
        elif self.current >= self.offset + rows:
            self.offset = self.current - rows + 1
        list_width = rect.width // 2 - 2 * margin
        for i, game in enumerate(
            self.games[self.offset : self.offset + rows], self.offset
        ):
            mark = "*" if game in self.captured else " "
            color = (0, 0, 0) if i == self.current else (255, 255, 255)
            y = top + (i - self.offset) * line_height
            if i == self.current:
                screen.fill((255, 255, 255), (margin, y, list_width, line_height))
            text = self.font.render(f"{mark} {game.identifier}", ANTIALIAS, color)
            screen.blit(text, (margin, y), (0, 0, list_width, line_height))

        # Preview of the captured title screen on the right half
        if self.games and (path := self.games[self.current].get_titlescreen()):
            if self.preview is None:
                self.preview = pg.image.load(path)
            area = pg.Rect(
                rect.width // 2,
                top,
                rect.width // 2 - margin,
                rect.height - top - margin,
            )
            w, h = self.preview.get_size()
            scale = min(area.width / w, area.height / h)
            image = pg.transform.scale(self.preview, (int(w * scale), int(h * scale)))
            screen.blit(image, image.get_rect(midtop=area.midtop))
