"""A single game."""

import configparser
import glob
import json
import shlex
import shutil
import ssl
import subprocess
import traceback
from collections import deque
from collections.abc import Callable
from configparser import RawConfigParser
from contextlib import suppress
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Literal, override
from urllib import request
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.parse import unquote
from zipfile import ZipFile

import pygame as pg

from .emulator import (
    NO_WINDOW,
    get_dosbox_command,
    get_dosbox_options,
    get_scummvm_command,
)
from .iso import ISOFile
from .utils import tls_context

QUICK_EXIT = 3  # seconds
OUTPUT_LINES = 5
EMULATOR_FAILED = pg.event.custom_type()
TITLESCREEN_SIZE = 320, 200
METADATA_CACHE = "metadata.json"

# Browsers make Windows fetch missing root certificates, Python doesn't.
CERTIFICATE_HINT = (
    "Visit https://archive.org/ in your web browser and then try again, it might help."
)

type Engine = Literal["dosbox", "scummvm"]


class MetadataError(Exception):
    """The metadata.ini or title.png of a game is missing or invalid."""


class Game:
    """A game with metadata and a title screen."""

    def __init__(self, path: Path, metadata: dict[str, str] | None = None) -> None:
        """Create the game from its metadata, or raise MetadataError."""
        self.path = path
        self.identifier = path.name
        self.download_thread: Download | None = None
        self.unzip_thread: Unzip | None = None
        self.emulator: Emulator | None = None
        self.thumbnails: dict[tuple[int, int], pg.Surface] = {}
        self.color: tuple[int, int, int] | None = None
        self.titlescreen = path / "title.png"
        try:
            self.configure(given=metadata)
        except (KeyError, ValueError, configparser.Error) as e:
            reason = f"Missing {e}" if isinstance(e, KeyError) else str(e)
            msg = f"Invalid metadata for {self.identifier}\n\n{reason}"
            raise MetadataError(msg) from e

    def configure(self, *, given: dict[str, str] | None) -> None:
        """Use the given metadata, or read metadata.ini and check for title.png."""
        self.config = RawConfigParser()
        if given is None:
            if not self.titlescreen.is_file():
                msg = "Missing title.png"
                raise ValueError(msg)
            self.config.read(self.path / "metadata.ini", encoding="utf-8")
        else:
            self.config.read_dict({"metadata": given})
        metadata = self.config["metadata"]
        self.title = metadata["title"]
        self.year = metadata["year"]
        self.urls = metadata["url"].split()
        self.size = metadata.getint("size")
        engine = metadata.get("engine", "dosbox")
        if engine not in ("dosbox", "scummvm"):
            msg = f"Unknown engine {engine!r}"
            raise ValueError(msg)
        self.engine: Engine = engine
        self.scummvm_game = metadata.get("scummvm_game")
        self.scummvm_args = (metadata.get("scummvm_args") or "").split()
        self.emulator_start = metadata.get("emulator_start")
        self.autoplayable = metadata.getboolean("autoplayable", fallback=True)
        datadir = "scummvm_data" if self.engine == "scummvm" else "dosbox_drive_c"
        self.gamedir = self.path / datadir

    def get_emulator(self) -> list[str]:
        """Return the emulator's command, or raise EmulatorError."""
        if self.engine == "scummvm":
            return get_scummvm_command()
        return get_dosbox_command()

    def start(self, *, autorun: bool = True) -> "Emulator":
        r"""Start the game and return the thread that runs the emulator.

        There are two modes:

        1. autorun=True

            Paste the contents of `emulator_start` into dosbox.bat, and
            run it. DOSBox will exit when the game ends.

        2. autorun=False

            Do as above, but don't run dosbox.bat and don't exit
            DOSBox.

        The frontend allows starting the game in the second mode by pressing
        Alt-Enter.

        Raises EmulatorError if DOSBox (or ScummVM) isn't installed.
        """
        if self.engine == "scummvm":
            return self.start_scummvm(autorun=autorun)

        dosbox = get_dosbox_command()
        dosbox_args = [".", *get_dosbox_options()]

        # Copy patch files to C:\
        for file in filter(Path.is_file, self.path.glob("patches/*")):
            shutil.copy(file, self.gamedir)

        if self.emulator_start:
            if autorun:
                dosbox_args[0] = "dosbox.bat"
                self.write_c("dosbox.bat", f"@echo off\ncls\n{self.emulator_start}\n")

            else:
                self.write_c("dosbox.bat", self.emulator_start + "\n")

        else:
            autorun = False

        if autorun:
            dosbox_args.append("-exit")

        # Hand the game over to the DOSBox thread
        command = [*dosbox, *dosbox_args]
        thread = DOSBox(self, command, autorun=autorun)
        thread.start()
        return thread

    def write_c(self, filename: str, text: str) -> None:
        r"""Write a text file to C:\."""
        (self.gamedir / filename).write_text(text, encoding="cp437", newline="\r\n")

    def start_scummvm(self, *, autorun: bool = True) -> "Emulator":
        """Start the game with ScummVM.

        Use `scummvm_game` as the target. Savegames are stored in the
        game directory. With autorun=False, the ScummVM launcher is
        opened instead.
        """
        scummvm = get_scummvm_command()
        args = ["--path=.", "--savepath=."]
        if autorun and self.scummvm_game:
            args.extend([*self.scummvm_args, self.scummvm_game])

        thread = Emulator(self, [*scummvm, *args])
        thread.start()
        return thread

    def set_cpu_cycles(self, cpu_cycles: int) -> None:
        """Set cpu_cycles at the top of `emulator_start`."""
        if not self.emulator_start:
            return
        line = f"config -set cpu_cycles={cpu_cycles}"
        lines = self.emulator_start.split("\n")
        top = 0 if lines[0] else 1
        if lines[top : top + 1] == [line]:
            return
        lines.insert(top, line)
        self.emulator_start = "\n".join(lines)
        self.save_metadata("emulator_start", self.emulator_start)

    def save_metadata(self, key: str, value: str) -> None:
        """Save the value to metadata.ini and the cache."""
        self.config["metadata"][key] = value
        with (self.path / "metadata.ini").open(
            "w", encoding="utf-8", newline="\n"
        ) as f:
            self.config.write(f)
        self.update_cache()

    def reload_metadata(self) -> bool:
        """Read metadata.ini again, and return whether the metadata changed.

        Raise MetadataError if it's invalid, and keep the old metadata.
        """
        metadata = dict(Game(self.path).config["metadata"])
        if metadata == dict(self.config["metadata"]):
            return False
        self.configure(given=metadata)
        self.update_cache()
        return True

    def update_cache(self) -> None:
        """Update the metadata of this game in the cache, if it's there."""
        cache = read_metadata_cache(self.path.parent)
        if self.identifier in cache:
            cache[self.identifier] = dict(self.config["metadata"])
            write_metadata_cache(self.path.parent, cache)

    def load_titlescreen(self) -> None:
        """Create thumbnails.

        Title screens wider than TITLESCREEN_SIZE keep their original
        size, and the next thumbnail is scaled down from that directly.
        The thumbnails appear all at once, so that another thread can
        load them while this one draws them.
        """
        image = pg.image.load(self.titlescreen)
        width, height = image.get_size()
        if width <= TITLESCREEN_SIZE[0] and (width, height) != TITLESCREEN_SIZE:
            image = pg.transform.smoothscale(image.convert(24), TITLESCREEN_SIZE)
        thumbnails = {TITLESCREEN_SIZE: image}
        image = image.convert(24)

        # The thumbnails form a mipmap pyramid, after Lance Williams,
        # "Pyramidal Parametrics" (SIGGRAPH 1983).
        width, height = TITLESCREEN_SIZE
        while (width, height) != (1, 1):
            width, height = (width + 1) // 2, (height + 1) // 2
            image = pg.transform.smoothscale(image, (width, height))
            thumbnails[width, height] = image
        red, green, blue, _ = image.get_at((0, 0))
        self.color = red, green, blue
        self.thumbnails = thumbnails

    def get_titlescreen(self, size: tuple[int, int]) -> pg.Surface | None:
        """Given the tile size, return the correct thumbnail, if loaded yet."""
        thumbnails = self.thumbnails
        for (width, height), thumbnail in reversed(thumbnails.items()):
            if size[0] <= width and size[1] <= height:
                return thumbnail
        return thumbnails.get(TITLESCREEN_SIZE)

    def is_ready(self) -> bool:
        """Return whether the game has been downloaded and unzipped."""
        unzipping = self.unzip_thread is not None and self.unzip_thread.is_alive()
        return self.gamedir.is_dir() and not unzipping

    def is_downloaded(self) -> bool:
        """Return whether the game has been downloaded or unzipped."""
        return self.is_ready() or all(
            file.is_file() for file in downloaded_filenames(self.urls, self.path)
        )

    def is_running(self) -> bool:
        """Return whether the game's emulator is running."""
        return self.emulator is not None and self.emulator.is_alive()

    def reset(self) -> None:
        """Delete the downloaded game, including its saved state."""
        if not self.is_ready():
            return
        shutil.rmtree(self.gamedir, ignore_errors=True)

    def download(self) -> None:
        """Start downloading the game in a new thread."""
        self.download_thread = Download(self.urls, self.gamedir, size=self.size)
        self.download_thread.start()

    def unzip(self) -> "Unzip":
        """Start unzipping the downloaded game in a new thread, unless it is.

        Return the thread that unzips it.
        """
        if self.unzip_thread is None or not self.unzip_thread.is_alive():
            # ScummVM can't read disc images, so extract them. DOSBox games
            # mount their disc images themselves.
            extract = self.engine == "scummvm"
            self.unzip_thread = Unzip(self.urls, self.gamedir, extract=extract)
            self.unzip_thread.start()
        return self.unzip_thread


class Emulator(Thread):
    """A thread that runs a game in an emulator."""

    def __init__(self, game: Game, command: list[str]) -> None:
        """Prepare to run the game with the given emulator command."""
        self.game = game
        self.command = command
        self.output: deque[str] = deque(maxlen=OUTPUT_LINES)
        self.returncode = 0
        self.process: subprocess.Popen[str] | None = None
        self.stopped = False
        super().__init__(daemon=True)

    def stop(self) -> None:
        """Stop the emulator."""
        self.stopped = True
        if self.process is not None:
            self.process.terminate()

    @override
    def run(self) -> None:
        """Run the emulator, pass on its output, and wait for it to exit."""
        print("Executing:", shlex.join(self.command))
        with subprocess.Popen(  # noqa: S603
            self.command,
            cwd=self.game.gamedir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            creationflags=NO_WINDOW,
        ) as process:
            self.process = process
            if self.stopped:
                process.terminate()
            for line in process.stdout or ():
                print(line, end="")
                self.output.append(line.rstrip())
        self.returncode = process.returncode


class DOSBox(Emulator):
    """A thread that runs a game in DOSBox."""

    def __init__(self, game: Game, command: list[str], *, autorun: bool) -> None:
        """Prepare to run the game in DOSBox, with or without autorun."""
        self.autorun = autorun
        super().__init__(game, command)

    @override
    def run(self) -> None:
        """Run DOSBox and report it if the game exits suspiciously quickly."""
        game = self.game
        started = monotonic()
        super().run()
        seconds = monotonic() - started

        if self.autorun and seconds < QUICK_EXIT and not self.stopped:
            message = (
                f"{game.title} exited in {seconds:.3f} seconds.\n\n"
                "This probably means its start command is wrong.\n"
                "Press Alt-Enter to open DOSBox and try to start\n"
                "the game manually. Good luck!"
            )
            if self.returncode:
                output = "\n".join(self.output)
                message += f"\n\nDOSBox exited with code {self.returncode}:\n{output}"
            pg.event.post(pg.event.Event(EMULATOR_FAILED, message=message))


class Job(Thread):
    """A thread that works on the files of a game."""

    def __init__(self, urls: list[str], gamedir: Path) -> None:
        """Prepare to work on the downloaded files of the URLs."""
        self.urls = urls
        self.gamedir = gamedir
        self.files = downloaded_filenames(urls, gamedir.parent)
        self.filename = ""
        self.action = ""
        self.error: str | None = None
        super().__init__(daemon=True)

    @override
    def run(self) -> None:
        """Do the work, and clean up if that fails or is cancelled."""
        try:
            self.work()
        except InterruptedError:
            print(" cancelled.")
        except Exception as e:  # noqa: BLE001 - a corrupt archive can raise anything
            self.fail(e)
        else:
            return
        self.clean_up()

    def work(self) -> None:
        """Do the work."""
        raise NotImplementedError

    def clean_up(self) -> None:
        """Remove what's left of the unfinished work."""

    def fail(self, error: Exception) -> None:
        """Record an action that failed, with the full error."""
        if type(error) is URLError and isinstance(error.reason, Exception):
            error = error.reason  # The actual error is inside
        if isinstance(error, HTTPError):
            reason = f"{error.code} {error.reason}"
        else:
            reason = "".join(traceback.format_exception_only(error)).strip()
        if isinstance(error, ssl.SSLCertVerificationError):
            reason += f"\n\n{CERTIFICATE_HINT}"
        self.error = f"Failed to {self.action} {self.filename}\n\n{reason}"
        print(" failed :(")


class Download(Job):
    """A thread that downloads a game, and can be cancelled."""

    def __init__(
        self, urls: list[str], gamedir: Path, *, size: int | None = None
    ) -> None:
        """Prepare to download the URLs next to gamedir."""
        super().__init__(urls, gamedir)
        self.size = size
        self.downloaded = 0
        self.step = 0
        self.steps = 1
        self.progress = 0.0
        self.action = "download"
        self.cancelled = Event()

    def cancel(self) -> None:
        """Cancel the download and wait for the thread to finish."""
        self.cancelled.set()
        self.join()

    @override
    def work(self) -> None:
        """Download each URL, unless it already was."""
        self.steps = 1 if self.size else len(self.files)
        for i, (u, dest) in enumerate(zip(self.urls, self.files, strict=True)):
            self.step = 0 if self.size else i
            self.filename = dest.name
            if dest.is_file():
                self.downloaded += dest.stat().st_size
            elif source := find_download(u, dest):
                print(f"Linking {dest.name} from {source.parent.name}")
                link_or_copy(source, dest)
                self.downloaded += dest.stat().st_size
            else:
                print(f"Downloading {u}", end="", flush=True)
                self.report(0, 0)
                self.request(u, dest)
                print(" done!")
        self.progress = 1.0

    def request(self, url: str, dest: Path) -> None:
        """Download the URL to dest, and remove dest if that fails."""
        try:
            self.fetch(url, dest)
        except BaseException:
            dest.unlink(missing_ok=True)
            raise

    def fetch(self, url: str, dest: Path) -> None:
        """Download the URL to dest, and print and report the progress."""
        with (
            request.urlopen(  # noqa: S310
                url, timeout=60, context=tls_context()
            ) as response,
            dest.open("wb") as f,
        ):
            total = int(response.headers.get("Content-Length") or 0)
            if total:
                print(f" ({total / 1e6:.1f}MB) ", end="", flush=True)
            done = dots = 0
            while block := response.read(1024 * 8):
                f.write(block)
                done += len(block)
                self.report(done, total)

                # Print one period per 0.1MB
                if new_dots := done // 100_000 - dots:
                    print("." * new_dots, end="", flush=True)
                    dots += new_dots
        if done < total:
            msg = f"retrieval incomplete: got only {done} out of {total} bytes"
            raise ContentTooShortError(msg, (str(dest), response.headers))
        self.downloaded += done

    def report(self, done: int, total: int) -> None:
        """Set progress to fraction of total progress, or stop if cancelled."""
        if self.cancelled.is_set():
            msg = "Download cancelled"
            raise InterruptedError(msg)
        if self.size:
            done, total = self.downloaded + done, self.size
        fraction = min(done / total, 1.0) if total > 0 else 0.0
        self.progress = (self.step + fraction) / self.steps


class Unzip(Job):
    """A thread that unzips a downloaded game into its game directory.

    It can't be cancelled, and quitting waits for it, so that a game is
    never left half unzipped.
    """

    def __init__(self, urls: list[str], gamedir: Path, *, extract: bool) -> None:
        """Prepare to unzip the downloaded files into gamedir."""
        super().__init__(urls, gamedir)
        self.daemon = False
        self.should_extract = extract

    @override
    def work(self) -> None:
        """Unzip (or copy) each downloaded file."""
        for dest in self.files:
            self.filename = filename = dest.name
            if self.should_extract and filename.lower().endswith((".iso", ".bin")):
                self.unpack("extract", dest, self.extract_iso)
            elif filename.lower().endswith((".zip", ".play")):
                self.unpack("unzip", dest, self.unzip)
            else:
                self.unpack("copy", dest, self.copy)

    @override
    def clean_up(self) -> None:
        """Remove the partially unzipped game."""
        shutil.rmtree(self.gamedir, ignore_errors=True)

    def unpack(
        self, action: str, archive: Path, method: Callable[[Path], None]
    ) -> None:
        """Unpack (or copy) the file with the given method, and print the result."""
        self.action = action
        print(f"Trying to {action} {archive.name}...", end="", flush=True)
        method(archive)
        print(" done!")

    def unzip(self, zipfile: Path) -> None:
        """Unzip the archive into the game directory."""
        with ZipFile(zipfile, "r") as f:
            f.extractall(self.gamedir)

    def copy(self, file: Path) -> None:
        """Link (or copy) the file into the game directory."""
        self.gamedir.mkdir(parents=True, exist_ok=True)
        link_or_copy(file, self.gamedir / file.name)

    def extract_iso(self, isofile: Path) -> None:
        """Extract the disc image into the game directory."""
        with ISOFile(isofile) as iso:
            for path, sector, size in iso.walk():
                iso.extract(sector, size, self.gamedir / path)


def downloaded_filenames(urls: list[str], directory: Path) -> list[Path]:
    """Return all downloaded filenames."""
    return [directory / unquote(u.split("/")[-1]).split("/")[-1] for u in urls]


def find_download(url: str, dest: Path) -> Path | None:
    """Return the file another game downloaded from the URL, if there is one."""
    games_dir = dest.parent.parent
    for file in games_dir.glob(f"*/{glob.escape(dest.name)}"):
        config = RawConfigParser()
        config.read(file.parent / "metadata.ini", encoding="utf-8")
        urls = config.get("metadata", "url", fallback="").split()
        if file.is_file() and url in urls:
            return file
    return None


def link_or_copy(source: Path, dest: Path) -> None:
    """Hard link dest to source, or copy it where hard links aren't possible."""
    try:
        dest.hardlink_to(source)
    except OSError:
        shutil.copy(source, dest)


def read_metadata_cache(games_dir: Path) -> dict[str, dict[str, str]]:
    """Return the cached metadata of all games, or nothing if it can't be read."""
    try:
        return json.loads((games_dir / METADATA_CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_metadata_cache(games_dir: Path, cache: dict[str, dict[str, str]]) -> None:
    """Cache the metadata of all games, unless the games are read-only."""
    with suppress(OSError):
        file = games_dir / METADATA_CACHE
        file.write_text(json.dumps(cache, indent=4), encoding="utf-8")
