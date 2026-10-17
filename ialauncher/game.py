"""A single game."""

import configparser
import shlex
import shutil
import ssl
import subprocess
import traceback
from collections.abc import Callable
from configparser import RawConfigParser
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Literal, override
from urllib import request
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.parse import unquote
from zipfile import ZipFile

import pygame as pg

from .emulator import get_dosbox_command, get_scummvm_command
from .iso import ISOFile
from .utils import tls_context

# A game that exits within this many seconds probably has a wrong start command.
QUICK_EXIT = 3
EMULATOR_FAILED = pg.event.custom_type()

# Browsers make Windows fetch missing root certificates, Python doesn't.
CERTIFICATE_HINT = (
    "Visit https://archive.org/ in your web browser and then try again, it might help."
)

type Engine = Literal["dosbox", "scummvm"]


class MetadataError(Exception):
    """The metadata.ini or title.png of a game is missing or invalid."""


class Game:
    """A game with metadata and a title screen."""

    def __init__(self, path: Path) -> None:
        """Create the game from its metadata, or raise MetadataError."""
        self.path = path
        self.identifier = path.name
        self.download_thread: Download | None = None
        self.cached_image: pg.Surface | None = None
        self.titlescreen = path / "title.png"
        try:
            self.configure()
        except (KeyError, ValueError, configparser.Error) as e:
            reason = f"Missing {e}" if isinstance(e, KeyError) else str(e)
            msg = f"Invalid metadata for {self.identifier}\n\n{reason}"
            raise MetadataError(msg) from e

    def configure(self) -> None:
        """Read the metadata from metadata.ini, and check for title.png."""
        if not self.titlescreen.is_file():
            msg = "Missing title.png"
            raise ValueError(msg)
        self.config = RawConfigParser()
        self.config.read(self.path / "metadata.ini")
        metadata = self.config["metadata"]
        self.title = metadata["title"]
        self.year = metadata["year"]
        self.urls = metadata["url"].split()
        engine = metadata.get("engine", "dosbox")
        if engine not in ("dosbox", "scummvm"):
            msg = f"Unknown engine {engine!r}"
            raise ValueError(msg)
        self.engine: Engine = engine
        self.scummvm_game = metadata.get("scummvm_game")
        self.scummvm_args = (metadata.get("scummvm_args") or "").split()
        self.emulator_start = metadata.get("emulator_start")
        self.dosbox_conf = metadata.get("dosbox_conf")
        datadir = "scummvm_data" if self.engine == "scummvm" else "dosbox_drive_c"
        self.gamedir = self.path / datadir

    def get_emulator(self) -> list[str]:
        """Return the emulator's command, or raise EmulatorError."""
        if self.engine == "scummvm":
            return get_scummvm_command()
        return get_dosbox_command()

    def start(self, *, autorun: bool = True) -> None:
        r"""Start the game.

        There are two modes:

        1. autorun=True

            Paste the contents of `emulator_start` into dosbox.bat, and
            run it. Dosbox will exit when the game ends.

        2. autorun=False

            Do as above, but don't run dosbox.bat and don't exit
            Dosbox. When Dosbox finishes, any changes made to
            dosbox.bat will be saved to the `emulator_start` variable
            in metadata.ini.

        The frontend allows starting the game in the second mode by pressing
        Alt-Enter. This allows the user to do the following from within dosbox:

            C:\> echo MYGAME.BAT >> dosbox.bat
            C:\> exit

        These changes will then be preserved for the next time the game
        is run normally.

        Raises EmulatorError if DOSBox (or ScummVM) isn't installed.
        """
        if self.engine == "scummvm":
            self.start_scummvm(autorun=autorun)
            return

        dosbox = get_dosbox_command()
        batfile = self.gamedir / "dosbox.bat"
        conffile = self.gamedir / "dosbox.conf"
        dosbox_args = [
            ".",
            "-fullscreen",
            "-userconf",
        ]  # Use --nolocalconf for DOSBox Staging

        if self.dosbox_conf:
            conffile.write_text(self.dosbox_conf)
            dosbox_args.extend(["-conf", "dosbox.conf"])

        if self.emulator_start:
            if autorun:
                dosbox_args[0] = "dosbox.bat"
                batfile.write_text("@echo off\ncls\n" + self.emulator_start)

            else:
                batfile.write_text(self.emulator_start)

        else:
            autorun = False
            if not batfile.is_file():
                # Provide empty dosbox.bat for easy autocomplete
                # (and correct filename capitalization!)
                batfile.write_text("\n")

        if autorun:
            dosbox_args.append("-exit")

        # Hand the game over to the DOSBox thread
        command = [*dosbox, *dosbox_args]
        DOSBox(self, command, batfile=batfile, autorun=autorun).start()

    def start_scummvm(self, *, autorun: bool = True) -> None:
        """Start the game with ScummVM.

        Use `scummvm_game` as the target. Savegames are stored in the
        game directory. With autorun=False, the ScummVM launcher is
        opened instead.
        """
        scummvm = get_scummvm_command()
        args = ["--path=.", "--savepath=."]
        if autorun and self.scummvm_game:
            args.extend([*self.scummvm_args, self.scummvm_game])

        Emulator(self, [*scummvm, *args]).start()

    def save_emulator_start(self, emulator_start: str) -> None:
        """Change emulator_start, and save it to metadata.ini."""
        self.emulator_start = emulator_start
        self.config["metadata"]["emulator_start"] = emulator_start
        with (self.path / "metadata.ini").open("w") as f:
            self.config.write(f)

    def is_ready(self) -> bool:
        """Return whether the game has been downloaded."""
        return self.gamedir.is_dir()

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
            self.urls, self.gamedir, unzip=unzip, extract=extract
        )
        self.download_thread.start()


class Emulator(Thread):
    """A thread that runs a game in an emulator."""

    def __init__(self, game: Game, command: list[str]) -> None:
        """Prepare to run the game with the given emulator command."""
        self.game = game
        self.command = command
        super().__init__(daemon=True)

    @override
    def run(self) -> None:
        """Run the emulator and wait for it to exit."""
        print("Executing:", shlex.join(self.command))
        subprocess.run(self.command, cwd=self.game.gamedir, check=False)  # noqa: S603


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

        if self.autorun and seconds < QUICK_EXIT:
            message = (
                f"{game.title} exited in {seconds:.3f} seconds.\n\n"
                "This probably means its start command is wrong.\n"
                "Press Alt-Enter to open DOSBox and try to start\n"
                "the game manually. Good luck!"
            )
            pg.event.post(pg.event.Event(EMULATOR_FAILED, message=message))

        if not self.autorun and self.batfile.is_file():
            emulator_start = self.batfile.read_text().rstrip("\r\n")
            if emulator_start and emulator_start != game.emulator_start:
                game.save_emulator_start(emulator_start)


class Download(Thread):
    """A thread that downloads a game and unzips it."""

    def __init__(
        self,
        urls: list[str],
        gamedir: Path,
        *,
        unzip: bool = True,
        extract: bool = False,
    ) -> None:
        """Prepare to download the URLs and unpack them into gamedir."""
        self.urls = urls
        self.gamedir = gamedir
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
        """Download each URL (unless it already was) and unpack it."""
        for u in self.urls:
            self.action = "download"
            self.filename = filename = unquote(u.split("/")[-1]).split("/")[-1]
            dest = self.gamedir.parent / filename
            if not dest.is_file():
                print(f"Downloading {u}", end="", flush=True)
                self.report(0, 0)
                self.request(u, dest)
                print(" done!")
            if not self.should_unzip:
                continue
            if self.should_extract and filename.lower().endswith((".iso", ".bin")):
                self.unpack("extract", dest, self.extract_iso)
            elif filename.lower().endswith((".zip", ".play")):
                self.unpack("unzip", dest, self.unzip)
            else:
                self.gamedir.mkdir(parents=True, exist_ok=True)
                shutil.copy(dest, self.gamedir)

    def unpack(
        self, action: str, archive: Path, method: Callable[[Path], None]
    ) -> None:
        """Unpack the archive with the given method, and print the result."""
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

    def report(self, done: int, total: int) -> None:
        """Update the progress, or stop if the download was cancelled."""
        if self.cancelled.is_set():
            msg = "Download cancelled"
            raise InterruptedError(msg)
        self.progress = min(done / total, 1.0) if total > 0 else 0.0

    def unzip(self, zipfile: Path) -> None:
        """Unzip the archive into the game directory."""
        with ZipFile(zipfile, "r") as f:
            members = f.infolist()
            total = sum(m.file_size for m in members)
            done = 0
            for m in members:
                self.report(done, total)
                f.extract(m, self.gamedir)
                done += m.file_size

    def extract_iso(self, isofile: Path) -> None:
        """Extract the disc image into the game directory."""
        with ISOFile(isofile) as iso:
            members = list(iso.walk())
            total = sum(size for _, _, size in members)
            done = 0

            def progress(n: int) -> None:
                nonlocal done
                done += n
                self.report(done, total)

            for path, sector, size in members:
                iso.extract(sector, size, self.gamedir / path, progress)
