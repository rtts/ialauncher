"""A single game."""

import configparser
import shutil
import subprocess
from collections.abc import Callable
from configparser import RawConfigParser
from http.client import HTTPException, RemoteDisconnected
from pathlib import Path
from threading import Event, Thread
from typing import TYPE_CHECKING, override
from urllib import request
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.parse import unquote
from zipfile import ZipFile

from . import options
from .emulator import get_dosbox_command, get_scummvm_command
from .iso import ISOFile

if TYPE_CHECKING:
    import pygame as pg

# What configure() raises when metadata.ini is missing or invalid
CONFIG_ERRORS = (KeyError, ValueError, configparser.Error)


class Game:
    """A game with metadata and a title screen."""

    def __init__(self, path: Path) -> None:
        """Create the game without reading its metadata yet."""
        self.path = path
        self.identifier = path.name
        self.configured = False
        self.download_thread: Download | None = None
        self.emulator_thread: Emulator | None = None
        self.cached_image: pg.Surface | None = None

    def configure(self) -> None:
        """Read the metadata from metadata.ini."""
        self.config = c = RawConfigParser()
        c.read(self.path / "metadata.ini")
        self.title = c["metadata"].get("title")
        self.year = c["metadata"].get("year")
        self.engine = c["metadata"].get("engine", "dosbox")
        self.scummvm_game = c["metadata"].get("scummvm_game")
        self.scummvm_args = (c["metadata"].get("scummvm_args") or "").split()
        datadir = "scummvm_data" if self.engine == "scummvm" else "dosbox_drive_c"
        self.gamedir = self.path / datadir
        self.emulator_start = c["metadata"].get("emulator_start")
        self.dosbox_conf = c["metadata"].get("dosbox_conf")
        self.urls = c["metadata"]["url"].split()
        self.configured = True

    def __lt__(self, other: "Game") -> bool:
        """Sort games by identifier, ignoring case."""
        return self.identifier.lower() < other.identifier.lower()

    def get_emulator(self) -> list[str]:
        """Return the emulator's command, or raise EmulatorError."""
        if not self.configured:
            self.configure()
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

        # Save our work and hand the game over to the Dosbox thread
        self.batfile = batfile
        self.autorun = autorun
        self.emulator_args = dosbox_args
        self.emulator_thread = DOSBox(self, dosbox)
        self.emulator_thread.start()

    def start_scummvm(self, *, autorun: bool = True) -> None:
        """Start the game with ScummVM.

        Use `scummvm_game` as the target. Savegames are stored in the
        game directory. With autorun=False, the ScummVM launcher is
        opened instead.
        """
        scummvm = get_scummvm_command()
        captures_dir = Path(options.captures_dir).expanduser()
        captures_dir.mkdir(parents=True, exist_ok=True)
        args = ["--path=.", "--savepath=.", f"--screenshotpath={captures_dir}"]
        if autorun and self.scummvm_game:
            args.extend([*self.scummvm_args, self.scummvm_game])

        self.emulator_args = args
        self.emulator_thread = Emulator(self, scummvm)
        self.emulator_thread.start()

    def is_running(self) -> bool:
        """Return whether the emulator is still running."""
        return self.emulator_thread is not None and self.emulator_thread.is_alive()

    def write_metadata(self) -> None:
        """Write the metadata back to metadata.ini."""
        if self.title:
            self.config["metadata"]["title"] = self.title
        if self.year:
            self.config["metadata"]["year"] = self.year
        if self.urls:
            self.config["metadata"]["url"] = "\n".join(self.urls)
        if self.emulator_start:
            self.config["metadata"]["emulator_start"] = self.emulator_start
        if self.dosbox_conf:
            self.config["metadata"]["dosbox_conf"] = self.dosbox_conf
        with (self.path / "metadata.ini").open("w") as f:
            self.config.write(f)

    def get_titlescreen(self) -> Path | None:
        """Return the path of the title screen, or None if there is none."""
        path = self.path / "title.png"
        if path.is_file():
            return path
        return None

    def is_ready(self) -> bool:
        """Return whether the game has been downloaded."""
        if not self.configured:
            try:
                self.configure()
            except CONFIG_ERRORS:
                return False
        return self.gamedir.is_dir()

    def reset(self) -> None:
        """Delete the downloaded game, including its saved state."""
        if not self.is_ready():
            return
        shutil.rmtree(self.gamedir, ignore_errors=True)

    def download(self, *, unzip: bool = True) -> None:
        """Start downloading the game in a new thread."""
        if not self.configured:
            try:
                self.configure()
            except CONFIG_ERRORS:
                return
        # ScummVM can't read disc images, so extract them. DOSBox games
        # mount their disc images themselves.
        extract = self.engine == "scummvm"
        self.download_thread = Download(
            self.urls, self.gamedir, unzip=unzip, extract=extract
        )
        self.download_thread.start()


class Emulator(Thread):
    """A thread that runs a game in an emulator."""

    def __init__(self, game: Game, executable: list[str]) -> None:
        """Prepare to run the game with the given emulator command."""
        self.game = game
        self.executable = executable
        super().__init__(daemon=True)

    @override
    def run(self) -> None:
        """Run the emulator and wait for it to exit."""
        game = self.game
        command = self.executable + game.emulator_args
        print("Executing:", " ".join(command))
        subprocess.run(command, cwd=game.gamedir, check=False)  # noqa: S603


class DOSBox(Emulator):
    """A thread that runs a game in DOSBox."""

    @override
    def run(self) -> None:
        """Run DOSBox, then save any changes to dosbox.bat."""
        super().run()
        game = self.game

        if not game.autorun and game.batfile.is_file():
            emulator_start = game.batfile.read_text().rstrip("\r\n")
            # Only rewrite metadata.ini if needed, because
            # rewriting it discards any comments.
            if emulator_start and emulator_start != game.emulator_start:
                game.emulator_start = emulator_start
                game.write_metadata()


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
        except TimeoutError:
            self.fail("timed out")
        except HTTPError as e:
            self.fail(f"{e.code} {e.reason}")
        except ContentTooShortError:
            self.fail("incomplete")
        except URLError as e:
            self.fail(str(e.reason))
        except RemoteDisconnected:
            self.fail("no answer")
        except (OSError, HTTPException) as e:
            self.fail(repr(e))
        else:
            return

        # Remove the partially unzipped or extracted game
        shutil.rmtree(self.gamedir, ignore_errors=True)

    def fail(self, error: str) -> None:
        """Remember why the download failed, and print it."""
        self.error = error
        print(f" {error} :(")

    def download(self) -> None:
        """Download each URL (unless it already was) and unpack it."""
        for u in self.urls:
            filename = unquote(u.split("/")[-1]).split("/")[-1]
            dest = self.gamedir.parent / filename
            if not dest.is_file():
                print(f"Downloading {u}", end="", flush=True)
                self.report(0, 0)
                self.request(u, dest)
                print(" done!")
            if not self.should_unzip:
                continue
            if self.should_extract and filename.lower().endswith((".iso", ".bin")):
                self.unpack("Extracting", dest, self.extract_iso)
            elif filename.lower().endswith((".zip", ".play")):
                self.unpack("Unzipping", dest, self.unzip)
            else:
                self.gamedir.mkdir(parents=True, exist_ok=True)
                shutil.copy(dest, self.gamedir)

    def unpack(self, verb: str, archive: Path, method: Callable[[Path], None]) -> None:
        """Unpack the archive with the given method, and print the result."""
        print(f"{verb} {archive.name}...", end="", flush=True)
        try:
            method(archive)
        except InterruptedError:
            raise
        except Exception:  # noqa: BLE001 - a corrupt archive can raise anything
            print(" failed.")
        else:
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
            request.urlopen(url, timeout=60) as response,  # noqa: S310
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
            msg = f"Download failed: got only {done} out of {total} bytes"
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
