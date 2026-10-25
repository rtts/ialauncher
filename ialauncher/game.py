"""A single game."""

import configparser
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
        self.dosbox_conf = metadata.get("dosbox_conf")
        self.cpu_cycles = metadata.getint("cpu_cycles")
        datadir = "scummvm_data" if self.engine == "scummvm" else "dosbox_drive_c"
        self.gamedir = self.path / datadir

    def get_emulator(self) -> list[str]:
        """Return the emulator's command, or raise EmulatorError."""
        if self.engine == "scummvm":
            return get_scummvm_command()
        return get_dosbox_command()

    def start(
        self, *, autorun: bool = True, cpu_cycles: int | None = None
    ) -> "Emulator":
        r"""Start the game and return the thread that runs the emulator.

        There are two modes:

        1. autorun=True

            Paste the contents of `emulator_start` into dosbox.bat, and
            run it. DOSBox will exit when the game ends.

        2. autorun=False

            Do as above, but don't run dosbox.bat and don't exit
            DOSBox. When DOSBox finishes, any changes made to
            dosbox.bat will be saved to the `emulator_start` variable
            in metadata.ini.

        The frontend allows starting the game in the second mode by pressing
        Alt-Enter. This allows the user to do the following from within DOSBox:

            C:\> echo MYGAME.BAT >> dosbox.bat
            C:\> exit

        These changes will then be preserved for the next time the game
        is run normally.

        Raises EmulatorError if DOSBox (or ScummVM) isn't installed.
        """
        if self.engine == "scummvm":
            return self.start_scummvm(autorun=autorun)

        dosbox = get_dosbox_command()
        batfile = self.gamedir / "dosbox.bat"
        dosbox_args = [".", *get_dosbox_options()]

        if cpu_cycles and cpu_cycles != self.cpu_cycles:
            self.cpu_cycles = cpu_cycles
            self.save_metadata("cpu_cycles", str(cpu_cycles))
        if self.cpu_cycles:
            dosbox_args.extend(["--set", f"cpu_cycles={self.cpu_cycles}"])

        if self.dosbox_conf:
            self.write_c("dosbox.conf", self.dosbox_conf)
            dosbox_args.extend(["-conf", "dosbox.conf"])

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
            if not batfile.is_file():
                # Provide empty dosbox.bat for easy autocomplete
                # (and correct filename capitalization!)
                self.write_c("dosbox.bat", "\n")

        if autorun:
            dosbox_args.append("-exit")

        # Hand the game over to the DOSBox thread
        command = [*dosbox, *dosbox_args]
        thread = DOSBox(self, command, batfile=batfile, autorun=autorun)
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

    def save_metadata(self, key: str, value: str) -> None:
        """Save the value to metadata.ini and the cache."""
        self.config["metadata"][key] = value
        with (self.path / "metadata.ini").open(
            "w", encoding="utf-8", newline="\n"
        ) as f:
            self.config.write(f)
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
        return self.gamedir.is_dir()

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

    def download(self, *, unzip: bool = True) -> None:
        """Start downloading the game in a new thread."""
        # ScummVM can't read disc images, so extract them. DOSBox games
        # mount their disc images themselves.
        extract = self.engine == "scummvm"
        self.download_thread = Download(
            self.urls, self.gamedir, size=self.size, unzip=unzip, extract=extract
        )
        self.download_thread.start()


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

    def __init__(
        self, game: Game, command: list[str], *, batfile: Path, autorun: bool
    ) -> None:
        """Prepare to run the game in DOSBox, with or without autorun."""
        self.batfile = batfile
        self.autorun = autorun
        super().__init__(game, command)

    @override
    def run(self) -> None:
        """Run DOSBox and save changes the user made to dosbox.bat."""
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

        if not self.autorun and self.batfile.is_file():
            batch = self.batfile.read_text(encoding="cp437")
            emulator_start = batch.rstrip("\r\n")
            if emulator_start and emulator_start != game.emulator_start:
                game.emulator_start = emulator_start
                game.save_metadata("emulator_start", emulator_start)


class Download(Thread):
    """A thread that downloads a game and unzips it."""

    def __init__(
        self,
        urls: list[str],
        gamedir: Path,
        *,
        size: int | None = None,
        unzip: bool = True,
        extract: bool = False,
    ) -> None:
        """Prepare to download the URLs and unpack them into gamedir."""
        self.urls = urls
        self.gamedir = gamedir
        self.size = size
        self.downloaded = 0
        self.step = 0
        self.steps = 1
        self.should_unzip = unzip
        self.should_extract = extract
        self.progress = 0.0
        self.filename = ""
        self.action = "download"
        self.error: str | None = None
        self.cancelled = Event()
        super().__init__(daemon=True)

    def cancel(self) -> None:
        """Cancel the download and wait for the thread to finish."""
        self.cancelled.set()
        self.join()

    @override
    def run(self) -> None:
        """Download the game, and clean up if that fails."""
        try:
            self.download()
        except InterruptedError:
            print(" cancelled.")
        except Exception as e:  # noqa: BLE001 - a corrupt archive can raise anything
            self.fail(e)
        else:
            return

        # Remove the partially unzipped or extracted game
        shutil.rmtree(self.gamedir, ignore_errors=True)

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

    def download(self) -> None:
        """Download each URL (unless it already was), then unpack them all."""
        files = downloaded_filenames(self.urls, self.gamedir.parent)
        self.action = "download"
        self.steps = 1 if self.size else len(files)
        for i, (u, dest) in enumerate(zip(self.urls, files, strict=True)):
            self.step = 0 if self.size else i
            self.filename = dest.name
            if not dest.is_file():
                print(f"Downloading {u}", end="", flush=True)
                self.report(0, 0)
                self.request(u, dest)
                print(" done!")
            else:
                self.downloaded += dest.stat().st_size
        self.progress = 1.0
        if not self.should_unzip:
            return
        for dest in files:
            self.filename = filename = dest.name
            if self.should_extract and filename.lower().endswith((".iso", ".bin")):
                self.unpack("extract", dest, self.extract_iso)
            elif filename.lower().endswith((".zip", ".play")):
                self.unpack("unzip", dest, self.unzip)
            else:
                self.unpack("copy", dest, self.copy)

    def unpack(
        self, action: str, archive: Path, method: Callable[[Path], None]
    ) -> None:
        """Unpack (or copy) the file with the given method, and print the result."""
        self.action = action
        print(f"Trying to {action} {archive.name}...", end="", flush=True)
        method(archive)
        print(" done!")

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
        self.check_cancelled("Download")
        if self.size:
            done, total = self.downloaded + done, self.size
        fraction = min(done / total, 1.0) if total > 0 else 0.0
        self.progress = (self.step + fraction) / self.steps

    def check_cancelled(self, action: str) -> None:
        """Stop if cancelled."""
        if self.cancelled.is_set():
            msg = f"{action} cancelled"
            raise InterruptedError(msg)

    def unzip(self, zipfile: Path) -> None:
        """Unzip the archive into the game directory, or stop if cancelled."""
        with ZipFile(zipfile, "r") as f:
            for member in f.infolist():
                self.check_cancelled("Unzip")
                f.extract(member, self.gamedir)

    def copy(self, file: Path) -> None:
        """Copy the file into the game directory."""
        self.gamedir.mkdir(parents=True, exist_ok=True)
        shutil.copy(file, self.gamedir)

    def extract_iso(self, isofile: Path) -> None:
        """Extract the disc image into the game directory."""
        with ISOFile(isofile) as iso:
            for path, sector, size in iso.walk():
                iso.extract(sector, size, self.gamedir / path)


def downloaded_filenames(urls: list[str], directory: Path) -> list[Path]:
    """Return all downloaded filenames."""
    return [directory / unquote(u.split("/")[-1]).split("/")[-1] for u in urls]


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
