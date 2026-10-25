"""Watch metadata.ini files for changes."""

import ctypes
import os
import select
import struct
import sys
from contextlib import suppress
from pathlib import Path
from threading import Lock, Thread
from typing import override

import pygame as pg

METADATA_CHANGED = pg.event.custom_type()
IN_CLOSE_WRITE = 0x8  # A file opened for writing was closed
IN_MOVED_TO = 0x80  # A file was moved into the directory, like editors save
IN_CLOEXEC = os.O_CLOEXEC
INOTIFY_EVENT = struct.Struct("iIII")  # wd, mask, cookie, len, followed by name
BUFFER_SIZE = 64 * 1024


class MetadataWatcher(Thread):
    """A thread that watches metadata.ini files.

    Only wakes on Linux (sorry Windows users!)
    """

    def __init__(self, game_dirs: list[Path]) -> None:
        """Prepare to watch the game directories."""
        self.game_dirs = game_dirs
        self.dirs: dict[int, Path] = {}  # By watch descriptor
        self.fd = -1
        self.changed_dirs: set[Path] = set()
        self.lock = Lock()
        self.stop_reading, self.stop_writing = os.pipe()
        super().__init__(daemon=True)

    @override
    def start(self) -> None:
        """Watch the game directories and start reading the events."""
        if sys.platform != "linux":
            return
        libc = ctypes.CDLL(None, use_errno=True)
        self.fd = libc.inotify_init1(IN_CLOEXEC)
        if self.fd < 0:
            return
        for game_dir in self.game_dirs:
            mask = IN_CLOSE_WRITE | IN_MOVED_TO
            wd = libc.inotify_add_watch(self.fd, os.fsencode(game_dir), mask)
            if wd >= 0:
                self.dirs[wd] = game_dir
        super().start()

    @override
    def run(self) -> None:
        """Read the events until stop() is called."""
        while self.fd in select.select([self.fd, self.stop_reading], [], [])[0]:
            self.collect(os.read(self.fd, BUFFER_SIZE))

    def collect(self, data: bytes) -> None:
        """Collect the directories of the changed metadata.ini files in the events."""
        changed = set()
        offset = 0
        while offset < len(data):
            wd, _, _, length = INOTIFY_EVENT.unpack_from(data, offset)
            offset += INOTIFY_EVENT.size
            name = data[offset : offset + length].rstrip(b"\0")
            offset += length
            if name == b"metadata.ini" and wd in self.dirs:
                changed.add(self.dirs[wd])
        if changed:
            with self.lock:
                self.changed_dirs |= changed
            with suppress(pg.error):  # pygame has quit
                pg.event.post(pg.event.Event(METADATA_CHANGED))

    def pop_changed(self) -> set[Path]:
        """Return the directories whose metadata.ini changed since the last call."""
        with self.lock:
            changed, self.changed_dirs = self.changed_dirs, set()
        return changed

    def stop(self) -> None:
        """Stop watching, and wait for the thread to finish."""
        os.write(self.stop_writing, b"\0")
        if self.is_alive():
            self.join()
        if self.fd >= 0:
            os.close(self.fd)
        os.close(self.stop_reading)
        os.close(self.stop_writing)
