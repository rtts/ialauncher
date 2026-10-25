"""Unit tests for downloading and starting games."""

import contextlib
import io
import socket
import ssl
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from ialauncher.game import CERTIFICATE_HINT, Download

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


class TestGame(unittest.TestCase):
    """Downloading a game."""

    def download(self, error: Exception) -> Download:
        """Run a download that fails with the given error, and return it."""
        download = Download([URL], Path("/path/to/gamedir"))
        with (
            mock.patch.object(Download, "request", side_effect=error),
            mock.patch("shutil.rmtree"),
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

    def test_failed_copy(self) -> None:
        """A file that isn't an archive is copied, which can fail too."""
        download = Download(["https://example.com/games/GAME.EXE"], Path("/path/to"))
        with (
            mock.patch.object(Download, "request"),
            mock.patch("pathlib.Path.mkdir"),
            mock.patch("shutil.copy", side_effect=OSError(28, "No space left")),
            mock.patch("shutil.rmtree"),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            download.run()
        self.assertEqual(
            download.error,
            "Failed to copy GAME.EXE\n\nOSError: [Errno 28] No space left",
        )
        self.assertEqual(
            stdout.getvalue(),
            "Downloading https://example.com/games/GAME.EXE done!\n"
            "Trying to copy GAME.EXE... failed :(\n",
        )
