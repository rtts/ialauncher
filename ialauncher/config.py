"""The user's configuration, stored in ialauncher.ini."""

import configparser
import os
import sys
from pathlib import Path

SECTION = "ialauncher"


def config_dir() -> Path:
    """Return the platform's usual place for our configuration."""
    home = Path.home()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or home / ".config"
    return Path(base) / "ialauncher"


def config_file() -> Path:
    """Return the path of ialauncher.ini."""
    return config_dir() / "ialauncher.ini"


def where_was_i_file() -> Path:
    """Return the path of where_was_i.txt, next to ialauncher.ini."""
    return config_file().parent / "where_was_i.txt"


def default_games_dir() -> Path:
    """Return the suggested games directory, in the home directory."""
    return Path.home() / "games"


def read_games_dir() -> Path | None:
    """Return the games directory from ialauncher.ini, if it's there."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_file(), encoding="utf-8")
    games_dir = config.get(SECTION, "games_dir", fallback=None)
    return Path(games_dir) if games_dir else None


def write_games_dir(games_dir: Path) -> None:
    """Save the games directory to ialauncher.ini, keeping any other settings."""
    path = config_file()
    config = configparser.ConfigParser(interpolation=None)
    config.read(path, encoding="utf-8")
    if not config.has_section(SECTION):
        config.add_section(SECTION)
    config.set(SECTION, "games_dir", str(games_dir))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        config.write(file)
