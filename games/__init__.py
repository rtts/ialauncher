"""The games, one directory per game with a metadata.ini and title.png.

Releases also include metadata.json, with the metadata of all games,
which IA Launcher reads instead of thousands of metadata.ini files.
"""

import json
from configparser import RawConfigParser
from pathlib import Path


def write_metadata(file: Path) -> None:
    """Write the metadata of all games to the file, or raise ValueError."""
    metadata = {}
    for ini in sorted(Path(__file__).parent.glob("*/metadata.ini")):
        if not ini.with_name("title.png").is_file():
            msg = f"Missing title.png for {ini.parent.name}"
            raise ValueError(msg)
        config = RawConfigParser()
        config.read(ini, encoding="utf-8")
        metadata[ini.parent.name] = dict(config["metadata"])
    file.write_text(json.dumps(metadata, indent=4), encoding="utf-8")
