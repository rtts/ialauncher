import os
import shutil
import subprocess
import sys
from configparser import RawConfigParser
from http.client import RemoteDisconnected
from threading import Event, Thread
from typing import override
from urllib import request
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.parse import unquote
from zipfile import ZipFile

import pygame as pg

from . import options
from .dosbox import get_dosbox_path
from .iso import ISOFile
from .scummvm import ScummVMNotFound, get_scummvm_path

DOSBOX = get_dosbox_path()
SCUMMVM: list[str] | None = None


class Game:
    def __init__(self, path: str) -> None:
        self.path = path
        self.identifier = os.path.basename(path)
        self.configured = False
        self.download_thread: Download | None = None
        self.emulator_thread: Emulator | None = None
        self.cached_image: pg.Surface | None = None

    def configure(self) -> None:
        self.config = c = RawConfigParser()
        c.read(os.path.join(self.path, "metadata.ini"))
        self.title = c["metadata"].get("title")
        self.year = c["metadata"].get("year")
        self.engine = c["metadata"].get("engine", "dosbox")
        self.scummvm_game = c["metadata"].get("scummvm_game")
        self.scummvm_args = (c["metadata"].get("scummvm_args") or "").split()
        datadir = "scummvm_data" if self.engine == "scummvm" else "dosbox_drive_c"
        self.gamedir = os.path.join(self.path, datadir)
        self.emulator_start = c["metadata"].get("emulator_start")
        self.dosbox_conf = c["metadata"].get("dosbox_conf")
        self.urls = c["metadata"]["url"].split()
        self.configured = True

    def __gt__(self, other: "Game") -> bool:
        return self.identifier.lower() > other.identifier.lower()

    def __lt__(self, other: "Game") -> bool:
        return self.identifier.lower() < other.identifier.lower()

    def start(self, autorun: bool = True) -> None:
        """
        Start the game in one of two modes:

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

            C:\\> echo MYGAME.BAT >> dosbox.bat
            C:\\> exit

        These changes will then be preserved for the next time the game
        is run normally.
        """

        if self.engine == "scummvm":
            self.start_scummvm(autorun)
            return

        batfile = os.path.join(self.gamedir, "dosbox.bat")
        conffile = os.path.join(self.gamedir, "dosbox.conf")
        dosbox_args = [
            ".",
            "-fullscreen",
            "-userconf",
        ]  # Use --nolocalconf for DOSBox Staging

        if self.dosbox_conf:
            with open(conffile, "w") as f:
                f.write(self.dosbox_conf)
            dosbox_args.extend(["-conf", "dosbox.conf"])

        if self.emulator_start:
            if autorun:
                dosbox_args[0] = "dosbox.bat"
                with open(batfile, "w") as f:
                    f.write("@echo off\ncls\n")
                    f.write(self.emulator_start)

            else:
                with open(batfile, "w") as f:
                    f.write(self.emulator_start)

        else:
            autorun = False
            if not os.path.isfile(batfile):

                # Provide empty dosbox.bat for easy autocomplete
                # (and correct filename capitalization!)
                with open(batfile, "w") as f:
                    f.write("\n")

        if autorun:
            dosbox_args.append("-exit")

        # Save our work and hand the game over to the Dosbox thread
        self.batfile = batfile
        self.autorun = autorun
        self.emulator_args = dosbox_args
        self.emulator_thread = DOSBox(self)
        self.emulator_thread.start()

    def start_scummvm(self, autorun: bool = True) -> None:
        """
        Start the game with ScummVM, using `scummvm_game` as the
        target. Savegames are stored in the game directory. With
        autorun=False, the ScummVM launcher is opened instead.
        """

        global SCUMMVM
        if SCUMMVM is None:
            try:
                SCUMMVM = get_scummvm_path()
            except ScummVMNotFound as e:
                print(e)
                return

        captures_dir = os.path.expanduser(options.captures_dir)
        os.makedirs(captures_dir, exist_ok=True)
        args = ["--path=.", "--savepath=.", f"--screenshotpath={captures_dir}"]
        if autorun and self.scummvm_game:
            args.extend(self.scummvm_args + [self.scummvm_game])

        self.emulator_args = args
        self.emulator_thread = Emulator(self, SCUMMVM)
        self.emulator_thread.start()

    def is_running(self) -> bool:
        return self.emulator_thread is not None and self.emulator_thread.is_alive()

    def write_metadata(self) -> None:
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
        inifile = os.path.join(self.path, "metadata.ini")
        with open(inifile, "w") as f:
            self.config.write(f)

    def get_titlescreen(self) -> str | None:
        path = os.path.join(self.path, "title.png")
        if os.path.isfile(path):
            return path
        else:
            return None

    def is_ready(self) -> bool:
        if not self.configured:
            try:
                self.configure()
            except:
                return False
        return os.path.isdir(self.gamedir)

    def reset(self) -> None:
        if not self.is_ready():
            return
        try:
            shutil.rmtree(self.gamedir)
        except:
            pass

    def download(self, unzip: bool = True) -> None:
        if not self.configured:
            try:
                self.configure()
            except:
                return
        # ScummVM can't read disc images, so extract them. DOSBox games
        # mount their disc images themselves.
        extract = self.engine == "scummvm"
        self.download_thread = Download(self.urls, self.gamedir, unzip, extract)
        self.download_thread.start()


class Emulator(Thread):
    def __init__(self, game: Game, executable: list[str]) -> None:
        self.game = game
        self.executable = executable
        super().__init__(daemon=True)

    @override
    def run(self) -> None:
        game = self.game
        command = self.executable + game.emulator_args
        print("Executing:", " ".join(command))
        subprocess.run(command, cwd=game.gamedir)


class DOSBox(Emulator):
    def __init__(self, game: Game) -> None:
        super().__init__(game, DOSBOX)

    @override
    def run(self) -> None:
        super().run()
        game = self.game

        if not game.autorun:
            if os.path.isfile(game.batfile):
                with open(game.batfile, "r") as f:
                    emulator_start = f.read().rstrip("\r\n")
                    # Only rewrite metadata.ini if needed, because
                    # rewriting it discards any comments.
                    if emulator_start and emulator_start != game.emulator_start:
                        game.emulator_start = emulator_start
                        game.write_metadata()


class Download(Thread):
    def __init__(
        self, urls: list[str], gamedir: str, unzip: bool = True, extract: bool = False
    ) -> None:
        self.urls = urls
        self.gamedir = gamedir
        self.should_unzip = unzip
        self.should_extract = extract
        self.progress = 0.0
        self.cancelled = Event()
        super().__init__(daemon=True)

    def cancel(self) -> None:
        self.cancelled.set()
        self.join()

    @override
    def run(self) -> None:
        try:
            self.download()
        except InterruptedError:
            print(" cancelled.")
        except TimeoutError:
            print(" timed out :(")
        except HTTPError as e:
            print(f" {e.code} {e.reason} :(")
        except ContentTooShortError:
            print(" incomplete :(")
        except URLError as e:
            print(f" {e.reason} :(")
        except RemoteDisconnected:
            print(" no answer :(")
        else:
            return

        # Remove the partially unzipped or extracted game
        shutil.rmtree(self.gamedir, ignore_errors=True)

    def download(self) -> None:
        for u in self.urls:
            filename = unquote(u.split("/")[-1]).split("/")[-1]
            dest = os.path.join(os.path.dirname(self.gamedir), filename)
            if not os.path.isfile(dest):
                print(f"Downloading {u}", end="", flush=True)
                self.report(0, 0)
                self.request(u, dest)
                print(" done!")
            if not self.should_unzip:
                continue
            if self.should_extract and filename.lower().endswith((".iso", ".bin")):
                print(f"Extracting {filename}...", end="", flush=True)
                try:
                    self.extract_iso(dest)
                    print(" done!")
                except InterruptedError:
                    raise
                except:
                    print(" failed.")
            elif filename.lower().endswith((".zip", ".play")):
                print(f"Unzipping {filename}...", end="", flush=True)
                try:
                    self.unzip(dest)
                    print(" done!")
                except InterruptedError:
                    raise
                except:
                    print(" failed.")
            else:
                os.makedirs(self.gamedir, exist_ok=True)
                shutil.copy(dest, self.gamedir)

    def request(self, url: str, dest: str) -> None:
        try:
            with request.urlopen(url, timeout=60) as response, open(dest, "wb") as f:
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
                raise ContentTooShortError(
                    f"Download failed: got only {done} out of {total} bytes",
                    (dest, response.headers),
                )
        except BaseException:
            if os.path.isfile(dest):
                os.remove(dest)
            raise

    def report(self, done: int, total: int) -> None:
        if self.cancelled.is_set():
            raise InterruptedError("Download cancelled")
        self.progress = min(done / total, 1.0) if total > 0 else 0.0

    def unzip(self, zipfile: str) -> None:
        with ZipFile(zipfile, "r") as f:
            members = f.infolist()
            total = sum(m.file_size for m in members)
            done = 0
            for m in members:
                self.report(done, total)
                f.extract(m, self.gamedir)
                done += m.file_size

    def extract_iso(self, isofile: str) -> None:
        with ISOFile(isofile) as iso:
            members = list(iso.walk())
            total = sum(size for _, _, size in members)
            done = 0

            def progress(n: int) -> None:
                nonlocal done
                done += n
                self.report(done, total)

            for path, sector, size in members:
                iso.extract(sector, size, os.path.join(self.gamedir, path), progress)
