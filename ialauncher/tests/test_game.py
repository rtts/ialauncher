"""Unit tests for downloading and starting games."""

import contextlib
import errno
import io
import socket
import ssl
import unittest
from email.message import Message
from http.client import BadStatusLine, IncompleteRead, RemoteDisconnected
from pathlib import Path
from unittest import mock
from urllib.error import ContentTooShortError, HTTPError, URLError

from ialauncher.game import CERTIFICATE_HINT, Download

URL = "https://example.com/games/Example%20Game%20%281992%29.zip"
MESSAGE = "Failed to download Example Game (1992).zip\n\n{}"
CERTIFICATE_EXPIRED = (
    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
    "certificate has expired (_ssl.c:1032)"
)
MISSING_ROOT = (
    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
    "unable to get local issuer certificate (_ssl.c:1032)"
)
DOWNLOAD_ERRORS: dict[str, tuple[Exception, str]] = {
    # It's always DNS:
    "unknown host": (
        URLError(socket.gaierror(-2, "Name or service not known")),
        "socket.gaierror: [Errno -2] Name or service not known",
    ),
    "no DNS server": (
        URLError(socket.gaierror(-3, "Temporary failure in name resolution")),
        "socket.gaierror: [Errno -3] Temporary failure in name resolution",
    ),
    "unknown host or no network (Windows)": (
        URLError(socket.gaierror(11001, "getaddrinfo failed")),
        "socket.gaierror: [Errno 11001] getaddrinfo failed",
    ),
    "no DNS answer (Windows)": (
        URLError(socket.gaierror(11002, "getaddrinfo failed")),
        "socket.gaierror: [Errno 11002] getaddrinfo failed",
    ),
    "other DNS error (Windows)": (
        URLError(socket.gaierror(11003, "getaddrinfo failed")),
        "socket.gaierror: [Errno 11003] getaddrinfo failed",
    ),
    # Connecting to the server:
    "connection timed out": (
        URLError(TimeoutError("timed out")),
        "TimeoutError: timed out",
    ),
    "connection timed out (Windows)": (
        URLError(TimeoutError(10060, "A connection attempt failed")),
        "TimeoutError: [Errno 10060] A connection attempt failed",
    ),
    "connection refused": (
        URLError(ConnectionRefusedError(111, "Connection refused")),
        "ConnectionRefusedError: [Errno 111] Connection refused",
    ),
    "connection refused (Windows)": (
        URLError(ConnectionRefusedError(10061, "No connection could be made")),
        "ConnectionRefusedError: [Errno 10061] No connection could be made",
    ),
    "network unreachable": (
        URLError(OSError(errno.ENETUNREACH, "Network is unreachable")),
        f"OSError: [Errno {errno.ENETUNREACH}] Network is unreachable",
    ),
    "no route to host": (
        URLError(OSError(errno.EHOSTUNREACH, "No route to host")),
        f"OSError: [Errno {errno.EHOSTUNREACH}] No route to host",
    ),
    "connection reset while connecting": (
        URLError(ConnectionResetError(104, "Connection reset by peer")),
        "ConnectionResetError: [Errno 104] Connection reset by peer",
    ),
    "connection reset while connecting (Windows)": (
        URLError(ConnectionResetError(10054, "An existing connection was closed")),
        "ConnectionResetError: [Errno 10054] An existing connection was closed",
    ),
    "certificate expired": (
        URLError(ssl.SSLCertVerificationError(1, CERTIFICATE_EXPIRED)),
        f"ssl.SSLCertVerificationError: {CERTIFICATE_EXPIRED}\n\n{CERTIFICATE_HINT}",
    ),
    "missing root certificate": (
        URLError(ssl.SSLCertVerificationError(1, MISSING_ROOT)),
        f"ssl.SSLCertVerificationError: {MISSING_ROOT}\n\n{CERTIFICATE_HINT}",
    ),
    "TLS error": (
        URLError(ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number")),
        "ssl.SSLError: [SSL: WRONG_VERSION_NUMBER] wrong version number",
    ),
    "proxy refused": (
        URLError(
            OSError("Tunnel connection failed: 407 Proxy Authentication Required")
        ),
        "OSError: Tunnel connection failed: 407 Proxy Authentication Required",
    ),
    "no host in URL": (
        URLError("no host given"),
        "urllib.error.URLError: <urlopen error no host given>",
    ),
    # The server's response:
    "forbidden": (
        HTTPError(URL, 403, "Forbidden", Message(), None),
        "403 Forbidden",
    ),
    "not found": (
        HTTPError(URL, 404, "Not Found", Message(), None),
        "404 Not Found",
    ),
    "too many requests": (
        HTTPError(URL, 429, "Too Many Requests", Message(), None),
        "429 Too Many Requests",
    ),
    "service unavailable": (
        HTTPError(URL, 503, "Service Unavailable", Message(), None),
        "503 Service Unavailable",
    ),
    "response timed out": (
        TimeoutError("timed out"),
        "TimeoutError: timed out",
    ),
    "closed before responding": (
        RemoteDisconnected("Remote end closed connection without response"),
        (
            "http.client.RemoteDisconnected: "
            "Remote end closed connection without response"
        ),
    ),
    "garbled response": (
        BadStatusLine("garbage"),
        "http.client.BadStatusLine: garbage",
    ),
    # Receiving the file:
    "connection dropped": (
        IncompleteRead(b"x" * 123, 456),
        "http.client.IncompleteRead: IncompleteRead(123 bytes read, 456 more expected)",
    ),
    "connection reset": (
        ConnectionResetError(104, "Connection reset by peer"),
        "ConnectionResetError: [Errno 104] Connection reset by peer",
    ),
    "TLS connection closed": (
        ssl.SSLEOFError(8, "EOF occurred in violation of protocol (_ssl.c:2427)"),
        "ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2427)",
    ),
    "file too short": (
        ContentTooShortError(
            "retrieval incomplete: got only 123 out of 456 bytes",
            ("Example Game (1992).zip", Message()),
        ),
        (
            "urllib.error.ContentTooShortError: "
            "<urlopen error retrieval incomplete: got only 123 out of 456 bytes>"
        ),
    ),
    # Writing the file:
    "no write permission": (
        PermissionError(13, "Permission denied", "/path/to/Example Game (1992).zip"),
        (
            "PermissionError: [Errno 13] Permission denied: "
            "'/path/to/Example Game (1992).zip'"
        ),
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
