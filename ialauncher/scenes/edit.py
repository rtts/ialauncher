"""The settings of a game, on top of its title screen."""

import shutil
import subprocess
from typing import override

import pygame as pg

from ialauncher import ega
from ialauncher.engine import NextScene
from ialauncher.game import NOT_APPLICABLE
from ialauncher.gamelist import gamelist

from . import BLACK, WHITE
from .hero import Hero

MARGIN = 16
CYCLES = ["300", "3000", "6000", "12000", "25000", "60000", "100000", "200000"]
SETTING_KEYS = {
    pg.K_1: ("core", ["simple", "normal", "dynamic"]),
    pg.K_2: ("cpu_cycles", CYCLES),
    pg.K_3: ("cpu_cycles_protected", [*CYCLES, "auto", NOT_APPLICABLE]),
}


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
    """Show the settings of the current game, and change them.

    1, 2 and 3 cycle through the values of core, cpu_cycles and
    cpu_cycles_protected, and save the new value right away. Ctrl-E
    opens metadata.ini in xjed.
    """

    @override
    def handle(self, event: pg.event.Event) -> NextScene:
        """Change a setting with 1, 2 or 3, or open xjed with Ctrl-E."""
        if event.type != pg.KEYDOWN:
            return super().handle(event)
        mod = event.mod & (pg.KMOD_CTRL | pg.KMOD_ALT | pg.KMOD_SHIFT)
        if mod & pg.KMOD_CTRL and event.key == pg.K_e:
            self.edit_metadata()
            return None
        if not mod and event.key in SETTING_KEYS:
            self.change_setting(*SETTING_KEYS[event.key])
            self.keystroke(event, typed=False)
            return None
        return super().handle(event)

    @staticmethod
    def change_setting(key: str, values: list[str]) -> None:
        """Switch the current DOSBox game's setting to the next value."""
        game = gamelist.get_current_game()
        if game and game.engine == "dosbox":
            value = next_value(game.dosbox_settings[key], values)
            game.set_dosbox_setting(key, value)

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
        lines = [f"{key} = {value}" for key, value in game.dosbox_settings.items()]
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
    def edit_metadata() -> None:
        """Open the current game's metadata.ini in xjed, if it's installed."""
        game = gamelist.get_current_game()
        if game and (editor := shutil.which("xjed")):
            subprocess.Popen([editor, game.path / "metadata.ini"])  # noqa: S603
