"""The settings of a game, on top of its title screen."""

import shutil
import subprocess
from typing import override

import pygame as pg

from ialauncher import ega
from ialauncher.engine import NextScene
from ialauncher.game import NOT_APPLICABLE, Game
from ialauncher.gamelist import gamelist

from . import BLACK, WHITE
from .browse import IDLE
from .hero import Hero

MARGIN = 16
CORES = {
    "simple": {
        "cpu_cycles": ["300"],
        "cpu_cycles_protected": [NOT_APPLICABLE],
    },
    "normal": {
        "cpu_cycles": ["3000", "6000", "12000"],
        "cpu_cycles_protected": [NOT_APPLICABLE],
    },
    "dynamic": {
        "cpu_cycles": ["25000", "60000", "100000"],
        "cpu_cycles_protected": ["auto", NOT_APPLICABLE],
    },
}
SETTING_KEYS = {pg.K_2: "cpu_cycles", pg.K_3: "cpu_cycles_protected"}


def next_value(value: str, values: list[str]) -> str:
    """Return the value after this one, or after the nearest smaller number."""
    if value in values:
        return values[(values.index(value) + 1) % len(values)]
    if value.isdigit():
        numbers = [v for v in values if v.isdigit() and int(v) > int(value)]
        if numbers:
            return numbers[0]
    return values[0]


class Edit(Hero):
    """Edit the settings of the current game.

    Temporary view, will remove later.
    """

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Change a setting with 1, 2 or 3, or open xjed with Ctrl-E.

        The screensaver doesn't start, not when idle and not with Delete.
        """
        if event.type == IDLE or (
            event.type == pg.KEYDOWN and event.key == pg.K_DELETE
        ):
            return None
        if event.type != pg.KEYDOWN:
            return super().handle(event)
        mod = event.mod & (pg.KMOD_CTRL | pg.KMOD_ALT | pg.KMOD_SHIFT)
        if mod & pg.KMOD_CTRL and event.key == pg.K_e:
            self.edit_metadata()
            return None
        if not mod and (event.key == pg.K_1 or event.key in SETTING_KEYS):
            game = gamelist.get_current_game()
            if game and game.engine == "dosbox":
                if event.key == pg.K_1:
                    self.change_core(game)
                else:
                    self.change_setting(game, SETTING_KEYS[event.key])
            self.keystroke(event, typed=False)
            return None
        return super().handle(event)

    @staticmethod
    def change_core(game: Game) -> None:
        """Switch to the next core, with the cycles that go with it."""
        core = next_value(game.dosbox_settings["core"], list(CORES))
        game.set_dosbox_setting("core", core)
        for key, values in CORES[core].items():
            if len(values) == 1 or key == "cpu_cycles":
                game.set_dosbox_setting(key, values[0])

    @staticmethod
    def change_setting(game: Game, key: str) -> None:
        """Switch the setting to its next value for the core, if it has one."""
        values = CORES.get(game.dosbox_settings["core"], {}).get(key, [])
        if len(values) > 1:
            game.set_dosbox_setting(key, next_value(game.dosbox_settings[key], values))

    @override
    def escape(self) -> NextScene:
        """Go back to Hero."""
        return Hero()

    @override
    def reload_changed(self) -> NextScene:
        """Stay in Edit when the metadata changes, to show the new settings."""
        next_scene = super().reload_changed()
        return Edit() if isinstance(next_scene, Hero) else next_scene

    @override
    def draw_overlays(self) -> None:
        """Draw the settings in the upper left corner."""
        super().draw_overlays()
        game = gamelist.get_current_game()
        if game is None or game.engine != "dosbox":
            return
        lines = [f"{game.title} ({game.year})"]
        lines.extend(f"{key} = {value}" for key, value in game.dosbox_settings.items())
        if game.emulator_start is not None:
            lines.append("emulator_start =")
            commands = game.emulator_start.strip("\n").split("\n")
            lines.extend(f"    {command}" for command in commands)
        lines.append(f"autoplay: {game.autoplay}")
        width = max(map(len, lines))
        top = MARGIN
        for line in lines:
            image = ega.render(line.ljust(width), WHITE, BLACK, (8, 2))
            self.screen.blit(image, (MARGIN, top))
            top += image.get_height()

    @staticmethod
    def where_was_i() -> None:
        """Jump to the game whose metadata was saved last."""
        if game := gamelist.get_current_game():
            file = game.path.parent / "where_was_i.txt"
            name = file.read_text(encoding="utf-8").strip() if file.exists() else ""
            for game in gamelist.all_games:
                if game.path.name == name:
                    gamelist.show_game(game)
                    break

    @staticmethod
    def edit_metadata() -> None:
        """Open the current game's metadata.ini in xjed, if it's installed."""
        game = gamelist.get_current_game()
        if game and (editor := shutil.which("xjed")):
            subprocess.Popen([editor, game.path / "metadata.ini"])  # noqa: S603
