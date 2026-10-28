"""The threads that download and unzip a game."""

import contextlib
import io
import socket
import ssl
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError
from zipfile import ZipFile

from ialauncher.game import CERTIFICATE_HINT, Download, Game, Unzip

URL = "https://example.com/games/Example%20Game%20%281992%29.zip"
MESSAGE = "Failed to download Example Game (1992).zip\n\n{}"
CERTIFICATE_EXPIRED = (
    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
    "certificate has expired (_ssl.c:1032)"
)
DOWNLOAD_ERRORS: dict[str, tuple[Exception, str]] = {
    "unknown host": (
        URLError(socket.gaierror(-2, "Name or service not known")),
        "socket.gaierror: [Errno -2] Name or service not known",
    ),
    "connection refused": (
        URLError(ConnectionRefusedError(111, "Connection refused")),
        "ConnectionRefusedError: [Errno 111] Connection refused",
    ),
    "certificate expired": (
        URLError(ssl.SSLCertVerificationError(1, CERTIFICATE_EXPIRED)),
        f"ssl.SSLCertVerificationError: {CERTIFICATE_EXPIRED}\n\n{CERTIFICATE_HINT}",
    ),
    "not found": (
        HTTPError(URL, 404, "Not Found", Message(), None),
        "404 Not Found",
    ),
    "connection reset": (
        ConnectionResetError(104, "Connection reset by peer"),
        "ConnectionResetError: [Errno 104] Connection reset by peer",
    ),
    "disk full": (
        OSError(28, "No space left on device"),
        "OSError: [Errno 28] No space left on device",
    ),
}


class TestDownload(unittest.TestCase):
    """The thread that downloads a game."""

    def download(self, error: Exception) -> Download:
        """Run a download that fails with the given error, and return it."""
        download = Download([URL], Path("/path/to/gamedir"))
        with (
            mock.patch.object(Download, "request", side_effect=error),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            download.run()
        return download

    def test_download_errors(self) -> None:
        """Each download error shows the full underlying error."""
        for name, (error, reason) in DOWNLOAD_ERRORS.items():
            with self.subTest(name):
                self.assertEqual(self.download(error).error, MESSAGE.format(reason))

    def test_cancelled_download(self) -> None:
        """Cancelling a download shows no error."""
        self.assertIsNone(self.download(InterruptedError("Download cancelled")).error)


class TestUnzip(unittest.TestCase):
    """The thread that unzips a game."""

    def setUp(self) -> None:
        """Make a directory for the downloaded files and the game directory."""
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.gamedir = self.dir / "dosbox_drive_c"

    def unzip(self, filename: str) -> Unzip:
        """Unzip the downloaded file, and return the thread."""
        unzip = Unzip(
            [f"https://example.com/games/{filename}"], self.gamedir, extract=False
        )
        with contextlib.redirect_stdout(io.StringIO()):
            unzip.run()
        return unzip

    def test_unzip(self) -> None:
        """A zip file is unzipped into the game directory."""
        with ZipFile(self.dir / "GAME.ZIP", "w") as f:
            f.writestr("GAME/GAME.EXE", "MZ")
        self.assertIsNone(self.unzip("GAME.ZIP").error)
        self.assertEqual((self.gamedir / "GAME" / "GAME.EXE").read_text(), "MZ")

    def test_copy(self) -> None:
        """A file that isn't an archive is copied into the game directory."""
        (self.dir / "GAME.EXE").write_text("MZ")
        self.assertIsNone(self.unzip("GAME.EXE").error)
        self.assertEqual((self.gamedir / "GAME.EXE").read_text(), "MZ")

    def test_corrupt(self) -> None:
        """A corrupt zip file fails, and leaves no game directory behind."""
        self.gamedir.mkdir()
        (self.dir / "GAME.ZIP").write_text("Not a zip")
        self.assertRegex(
            self.unzip("GAME.ZIP").error or "", "^Failed to unzip GAME.ZIP"
        )
        self.assertFalse(self.gamedir.exists())

    def test_failed_copy(self) -> None:
        """Copying can fail too, with the full error."""
        unzip = Unzip(
            ["https://example.com/games/GAME.EXE"], Path("/path/to"), extract=False
        )
        with (
            mock.patch("pathlib.Path.mkdir"),
            mock.patch("shutil.copy", side_effect=OSError(28, "No space left")),
            mock.patch("shutil.rmtree"),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            unzip.run()
        self.assertEqual(
            unzip.error,
            "Failed to copy GAME.EXE\n\nOSError: [Errno 28] No space left",
        )
        self.assertEqual(
            stdout.getvalue(),
            "Trying to copy GAME.EXE... failed :(\n",
        )


class TestGame(unittest.TestCase):
    """A game, while it's being unzipped."""

    def test_one_unzip(self) -> None:
        """A game that's being unzipped isn't ready, and isn't unzipped twice."""
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        metadata = {"title": "Game", "year": "1990", "url": "https://example.com/G.ZIP"}
        game = Game(directory, metadata)
        game.gamedir.mkdir()
        release = threading.Event()
        with mock.patch.object(Unzip, "work", lambda _: release.wait()):
            thread = game.unzip()
            self.assertIs(game.unzip(), thread)
            self.assertFalse(game.is_ready())
            release.set()
            thread.join()
        self.assertTrue(game.is_ready())
