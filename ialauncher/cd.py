"""Play CD audio."""

import random
import re
from array import array
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from threading import Event, Lock, Thread

import pygame as pg

import games

SECTOR = 2352
FRAMES_PER_SECOND = 75
GAMES_DIR = Path(games.__file__).parent
POLL_INTERVAL = 0.1
MIN_SECONDS = 10
MAX_SECONDS = 25 * 60
CHECKED_SAMPLES = 8 * SECTOR // 2
FILE_LINE = re.compile(r'\s*FILE\s+(?:"([^"]*)"|(\S+))', re.IGNORECASE)
TRACK_LINE = re.compile(r"\s*TRACK\s+(\d+)\s+(\S+)", re.IGNORECASE)
INDEX_LINE = re.compile(r"\s*INDEX\s+0*1\s+(\d+):(\d+):(\d+)", re.IGNORECASE)


@dataclass
class Track:
    """A track on a CD image, spanning a range of sectors in a file."""

    number: int
    mode: str
    file: Path
    start: int = 0
    end: int = 0

    def __str__(self) -> str:
        """Return the track number and its length in minutes and seconds."""
        minutes, seconds = divmod(round(self.seconds), 60)
        return f"track {self.number} ({minutes}:{seconds:02})"

    @property
    def seconds(self) -> float:
        """Return the length of the track in seconds."""
        return (self.end - self.start) / FRAMES_PER_SECOND

    @property
    def playable(self) -> bool:
        """Return whether this is an audio track of reasonable length."""
        return (
            self.mode == "AUDIO"
            and MIN_SECONDS <= self.seconds <= MAX_SECONDS
            and self.file.is_file()
        )

    def sound(self) -> pg.mixer.Sound:
        """Return the track as sound."""
        with self.file.open("rb") as f:
            f.seek(self.start * SECTOR)
            samples = array("h", f.read((self.end - self.start) * SECTOR))

        # Detect endianness by comparing the sum of differences between
        # consecutive samples before and after byte-swapping them. If the
        # latter is smaller, the audio is big endian. Thanks, Carmageddon.
        middle = len(samples) // 4 * 2
        original = samples[middle : middle + CHECKED_SAMPLES]
        swapped = array("h", original)
        swapped.byteswap()
        pair = original, swapped
        jumps = [sum(abs(a - b) for a, b in pairwise(s[::2])) for s in pair]
        if jumps[1] < jumps[0]:
            samples.byteswap()

        return pg.mixer.Sound(buffer=samples)


class CD:
    """An audio CD, read from a cue sheet."""

    def __init__(self, cue: Path, title: str | None = None) -> None:
        """Read the cue sheet and put the playable tracks in the playlist."""
        self.cue = cue
        self.title = title or cue.stem
        self.tracks = self.read_cue()
        self.playlist = [track for track in self.tracks if track.playable]

    def read_cue(self) -> list[Track]:
        """Return the tracks in the cue sheet with their sector ranges."""
        try:
            lines = self.cue.read_text(encoding="latin-1").splitlines()
        except OSError:
            return []
        tracks: list[Track] = []
        file = self.cue
        for line in lines:
            if match := FILE_LINE.match(line):
                quoted, bare = match.groups()
                file = self.locate(quoted or bare)
            elif match := TRACK_LINE.match(line):
                number, mode = match.groups()
                tracks.append(Track(int(number), mode.upper(), file))
            elif (match := INDEX_LINE.match(line)) and tracks:
                minutes, seconds, frames = map(int, match.groups())
                tracks[-1].start = (minutes * 60 + seconds) * FRAMES_PER_SECOND + frames
        for track, following in zip(tracks, [*tracks[1:], None], strict=True):
            if following is not None and following.file == track.file:
                track.end = following.start
            elif track.file.is_file():
                track.end = track.file.stat().st_size // SECTOR
        return tracks

    def locate(self, name: str) -> Path:
        """Return the file named in the cue sheet, ignoring differences in case."""
        path = self.cue.parent / name.replace("\\", "/")
        if path.is_file() or not path.parent.is_dir():
            return path
        lower = path.name.lower()
        return next((p for p in path.parent.iterdir() if p.name.lower() == lower), path)

    def step(self, track: Track, steps: int) -> Track:
        """Return the playable track the given number of steps away, wrapping around."""
        index = self.playlist.index(track) + steps
        return self.playlist[index % len(self.playlist)]


class Jukebox(Thread):
    """Play random tracks from random CDs beneath the games directory."""

    def __init__(self) -> None:
        """Prepare to play CDs."""
        super().__init__(daemon=True)
        self.cd: CD | None = None
        self.current: Track | None = None
        self.cued: Track | None = None
        self.channel: pg.mixer.Channel | None = None
        self.paused = False
        self.stopped = Event()
        self.lock = Lock()

    def cds(self) -> list[CD]:
        """Return the CDs beneath the games directory that have playable tracks."""
        cds = [
            CD(path, path.relative_to(GAMES_DIR).parts[0])
            for path in GAMES_DIR.glob("*/**/*")
            if path.suffix.lower() == ".cue"
        ]
        return [cd for cd in cds if cd.playlist]

    def run(self) -> None:
        """Keep playing the cued track, or else a random track from a random CD."""
        if pg.mixer.get_init() is None:
            return
        cds = self.cds()
        while cds:
            with self.lock:
                cd = self.cd
                if self.cued is None or cd is None:
                    cd = self.cd = random.choice(cds)  # noqa: S311
                    self.cued = random.choice(cd.playlist)  # noqa: S311
                track = self.cued
            try:
                sound = track.sound()
            except (OSError, pg.error):
                return
            with self.lock:
                if self.stopped.is_set():
                    return
                if self.cued is not track:
                    continue
                self.cued = None
                self.current = track
                channel = self.channel = sound.play()
                if self.paused:
                    channel.pause()
                print(f"Now playing: {cd.title}, {track}")
            while channel.get_busy():
                if self.stopped.wait(POLL_INTERVAL):
                    return

    def skip(self, steps: int) -> None:
        """Cue the track the given number of steps away on the current CD."""
        with self.lock:
            here = self.cued or self.current
            if self.cd is None or here is None:
                return
            self.cued = self.cd.step(here, steps)
            if self.channel is not None:
                self.channel.stop()

    def next(self) -> None:
        """Skip to the next track."""
        self.skip(1)

    def previous(self) -> None:
        """Go back to the previous track."""
        self.skip(-1)

    def pause(self) -> None:
        """Pause the current track."""
        with self.lock:
            self.paused = True
            if self.channel is not None:
                self.channel.pause()

    def resume(self) -> None:
        """Resume the current track."""
        with self.lock:
            self.paused = False
            if self.channel is not None:
                self.channel.unpause()

    def stop(self) -> None:
        """Stop the music."""
        with self.lock:
            self.stopped.set()
            if self.channel is not None and pg.mixer.get_init():
                self.channel.stop()
