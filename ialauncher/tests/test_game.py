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

from ialauncher.game import Download

URL = "https://example.com/games/Example%20Game%20%281992%29.zip"
GAMEDIR = Path("/path/to/gamedir")
MESSAGE = "Failed to download Example Game (1992).zip\n\n{}"
DOWNLOAD_ERRORS: dict[str, tuple[Exception, str]] = {
    # It's always DNS:
    "unknown host": (
        URLError(socket.gaierror(-2, "Name or service not known")),
        "Name or service not known",
    ),
    "no DNS server": (
        URLError(socket.gaierror(-3, "Temporary failure in name resolution")),
        "Temporary failure in name resolution",
    ),
    "unknown host or no network (Windows)": (
        URLError(socket.gaierror(11001, "getaddrinfo failed")),
        "Temporary failure in name resolution",
    ),
    "no DNS answer (Windows)": (
        URLError(socket.gaierror(11002, "getaddrinfo failed")),
        "Temporary failure in name resolution",
    ),
    "other DNS error (Windows)": (
        URLError(socket.gaierror(11003, "getaddrinfo failed")),
        "Temporary failure in name resolution",
    ),
    # Connecting to the server:
    "connection timed out": (
        URLError(TimeoutError("timed out")),
        "The connection timed out",
    ),
    "connection timed out (Windows)": (
        URLError(TimeoutError(10060, "A connection attempt failed")),
        "The connection timed out",
    ),
    "connection refused": (
        URLError(ConnectionRefusedError(111, "Connection refused")),
        "Connection refused",
    ),
    "connection refused (Windows)": (
        URLError(ConnectionRefusedError(10061, "No connection could be made")),
        "Connection refused",
    ),
    "network unreachable": (
        URLError(OSError(errno.ENETUNREACH, "Network is unreachable")),
        "Network is unreachable",
    ),
    "no route to host": (
        URLError(OSError(errno.EHOSTUNREACH, "No route to host")),
        "No route to host",
    ),
    "connection reset while connecting": (
        URLError(ConnectionResetError(104, "Connection reset by peer")),
        "Connection reset by peer",
    ),
    "connection reset while connecting (Windows)": (
        URLError(ConnectionResetError(10054, "An existing connection was closed")),
        "Connection reset by peer",
    ),
    "certificate expired": (
        URLError(
            ssl.SSLCertVerificationError(
                1,
                "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                "certificate has expired (_ssl.c:1032)",
            )
        ),
        "TLS certificate error",
    ),
    "TLS error": (
        URLError(ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number")),
        "TLS certificate error",
    ),
    "proxy refused": (
        URLError(
            OSError("Tunnel connection failed: 407 Proxy Authentication Required")
        ),
        "Tunnel connection failed: 407 Proxy Authentication Required",
    ),
    "no host in URL": (
        URLError("no host given"),
        "No host given",
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
        "The connection timed out",
    ),
    "closed before responding": (
        RemoteDisconnected("Remote end closed connection without response"),
        "Connection reset by peer",
    ),
    "garbled response": (
        BadStatusLine("garbage"),
        "BadStatusLine('garbage')",
    ),
    # Receiving the file:
    "connection dropped": (
        IncompleteRead(b"x" * 123, 456),
        "Transferred a partial file",
    ),
    "connection reset": (
        ConnectionResetError(104, "Connection reset by peer"),
        "Connection reset by peer",
    ),
    "TLS connection closed": (
        ssl.SSLEOFError(8, "EOF occurred in violation of protocol (_ssl.c:2427)"),
        "Connection reset by peer",
    ),
    "file too short": (
        ContentTooShortError(
            "got only 123 out of 456 bytes", ("Example Game (1992).zip", Message())
        ),
        "Transferred a partial file",
    ),
    # Writing the file:
    "no write permission": (
        PermissionError(13, "Permission denied"),
        f"Not allowed to write to {GAMEDIR.parent}",
    ),
    "disk full": (
        OSError(28, "No space left on device"),
        "No space left on device",
    ),
}


class TestGame(unittest.TestCase):
    """Downloading a game."""

    def download(self, error: Exception) -> Download:
        """Run a download that fails with the given error, and return it."""
        download = Download([URL], GAMEDIR)
        with (
            mock.patch.object(Download, "request", side_effect=error),
            mock.patch("shutil.rmtree"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            download.run()
        return download

    def test_download_errors(self) -> None:
        """Each download error shows the reason why the download failed."""
        for name, (error, reason) in DOWNLOAD_ERRORS.items():
            with self.subTest(name):
                self.assertEqual(self.download(error).error, MESSAGE.format(reason))

    def test_cancelled_download(self) -> None:
        """Cancelling a download shows no error."""
        self.assertIsNone(self.download(InterruptedError("Download cancelled")).error)
