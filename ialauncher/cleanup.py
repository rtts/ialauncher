"""Clean up the games directory."""

import filecmp
import re
import shutil
from collections import defaultdict
from configparser import RawConfigParser, SectionProxy
from dataclasses import dataclass, field
from pathlib import Path

from .game import (
    METADATA_DIR,
    downloaded_filenames,
    read_metadata_cache,
    write_metadata_cache,
)

DATADIRS = ("dosbox_drive_c", "scummvm_data", "qemu_data")


@dataclass
class Plan:
    """What cleaning up the games directory would do."""

    games_dir: Path
    stale_dirs: list[Path] = field(default_factory=list)
    stale_entries: list[Path] = field(default_factory=list)
    sizes: list[tuple[str, str, int]] = field(default_factory=list)
    links: list[tuple[Path, Path, int]] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return whether there's nothing to clean up."""
        return not (self.stale_dirs or self.stale_entries or self.sizes or self.links)


def cleanup(games_dir: Path) -> None:
    """Show what cleaning up the games directory would do, and do it if confirmed."""
    plan = make_plan(games_dir)
    print_plan(plan)
    if plan.is_empty():
        print("Nothing to clean up.")
        return
    if confirm("Proceed?"):
        execute(plan)
        print("Done!")


def confirm(question: str) -> bool:
    """Ask the user a yes/no question, defaulting to no."""
    try:
        return input(f"{question} [y/N] ").strip().lower() == "y"
    except EOFError:
        return False


def read_metadata() -> dict[str, SectionProxy]:
    """Return the metadata of all games, by identifier."""
    metadata = {}
    for ini in METADATA_DIR.glob("*/metadata.ini"):
        config = RawConfigParser()
        config.read(ini, encoding="utf-8")
        metadata[ini.parent.name] = config["metadata"]
    return metadata


def make_plan(games_dir: Path) -> Plan:
    """Find stale directories and downloads, incorrect sizes, and duplicates."""
    plan = Plan(games_dir)
    metadata = read_metadata()
    plan.stale_dirs = sorted(
        path
        for path in games_dir.iterdir()
        if path.is_dir() and path.name not in metadata
    )
    candidates: list[Path] = []
    for name, meta in sorted(metadata.items()):
        gamedir = games_dir / name
        if not gamedir.is_dir():
            continue
        files = downloaded_filenames(meta.get("url", "").split(), gamedir)
        names = {file.name for file in files}
        plan.stale_entries += sorted(
            entry
            for entry in gamedir.iterdir()
            if not (entry.is_file() and entry.name in names)
            and not (entry.is_dir() and entry.name in DATADIRS)
        )
        present = [file for file in files if file.is_file()]
        candidates += present
        candidates += [
            gamedir / datadir / file.name
            for file in present
            for datadir in DATADIRS
            if (gamedir / datadir / file.name).is_file()
        ]
        if files and len(present) == len(files) and "size" in meta:
            actual = sum(file.stat().st_size for file in files)
            if meta["size"] != str(actual):
                plan.sizes.append((name, meta["size"], actual))
    plan.links = find_links(list(dict.fromkeys(candidates)))
    return plan


def find_links(files: list[Path]) -> list[tuple[Path, Path, int]]:
    """Return (target, path, freed) for each identical file to hard link."""
    by_size = defaultdict(list)
    for file in files:
        by_size[file.stat().st_size].append(file)
    links = []
    for size, same_size in by_size.items():
        for inodes in identical_files(same_size):
            target = max(inodes, key=lambda paths: paths[0].stat().st_nlink)[0]
            for paths in inodes:
                if target in paths:
                    continue
                freed = size if paths[0].stat().st_nlink == len(paths) else 0
                links += [
                    (target, path, freed if i == 0 else 0)
                    for i, path in enumerate(paths)
                ]
    return links


def identical_files(files: list[Path]) -> list[list[list[Path]]]:
    """Group the files by contents, then by inode, keeping groups of 2+ inodes."""
    inodes = defaultdict(list)
    for file in files:
        stat = file.stat()
        inodes[stat.st_dev, stat.st_ino].append(file)
    groups: list[list[list[Path]]] = []
    for paths in inodes.values():
        for group in groups:
            if filecmp.cmp(group[0][0], paths[0], shallow=False):
                group.append(paths)
                break
        else:
            groups.append([paths])
    return [group for group in groups if len(group) > 1]


def unique_size(path: Path) -> int:
    """Return the space that removing the file or directory frees."""
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    return sum(
        stat.st_size for stat in (file.lstat() for file in files) if stat.st_nlink == 1
    )


def human(size: float) -> str:
    """Return the size in bytes as a human-readable string."""
    for unit in ("B", "KiB", "MiB"):
        if size < 1024:  # noqa: PLR2004
            return f"{size} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def print_plan(plan: Plan) -> None:
    """Print what cleaning up would do."""
    games_dir = plan.games_dir
    stale_dirs_size = stale_entries_size = 0
    for path in plan.stale_dirs:
        size = unique_size(path)
        stale_dirs_size += size
        print(f"Remove stale directory {path.relative_to(games_dir)} ({human(size)})")
    for path in plan.stale_entries:
        size = unique_size(path)
        stale_entries_size += size
        print(f"Remove stale {path.relative_to(games_dir)} ({human(size)})")
    for name, size, actual in plan.sizes:
        print(f"Update size of {name} from {size} to {actual}")
    for target, path, _ in plan.links:
        print(f"Link {path.relative_to(games_dir)} to {target.relative_to(games_dir)}")
    links_size = sum(freed for _, _, freed in plan.links)
    print()
    print(f"{len(plan.stale_dirs)} stale directories ({human(stale_dirs_size)})")
    print(f"{len(plan.stale_entries)} stale downloads ({human(stale_entries_size)})")
    print(f"{len(plan.sizes)} incorrect sizes")
    print(f"{len(plan.links)} duplicate files to link ({human(links_size)})")
    total = stale_dirs_size + stale_entries_size + links_size
    print(f"Total space to free: {human(total)}")
    print()


def execute(plan: Plan) -> None:
    """Clean up the games directory according to the plan."""
    for path in [*plan.stale_dirs, *plan.stale_entries]:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    if plan.sizes:
        update_sizes(plan.sizes)
    for target, path, _ in plan.links:
        temp = path.with_name(path.name + ".cleanup")
        temp.unlink(missing_ok=True)
        temp.hardlink_to(target)
        temp.replace(path)


def update_sizes(sizes: list[tuple[str, str, int]]) -> None:
    """Replace the sizes in metadata.ini and in the metadata cache, if any."""
    cache = read_metadata_cache(METADATA_DIR)
    for name, _, actual in sizes:
        ini = METADATA_DIR / name / "metadata.ini"
        text = ini.read_text(encoding="utf-8")
        text = re.sub(
            r"^size = .*$", f"size = {actual}", text, count=1, flags=re.MULTILINE
        )
        ini.write_text(text, encoding="utf-8", newline="\n")
        if name in cache:
            cache[name]["size"] = str(actual)
    if cache:
        write_metadata_cache(METADATA_DIR, cache)
