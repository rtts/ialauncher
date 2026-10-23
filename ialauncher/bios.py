"""Basic Input/Output System."""

import re
from array import array
from functools import cache
from typing import NamedTuple

import pygame as pg

# A few interesting facts about 882 Hz:
# - It produces exactly 50 samples per wave at 44.1 kHz
# - It was chosen to prevent undertones due to aliasing
# - It is 3.9 cents sharp of note A5 in concert pitch
# - It is 28.1 cents flat of the original IBM PC's power-on beep
BEEP_FREQUENCY = 882
BEEP_AMPLITUDE = 4096
held_keys: set[int] = set()


def kb_int(event: pg.event.Event) -> bool:
    """Return whether to handle the event, like the BIOS keyboard interrupt.

    Handle one keystroke per frame. When more come in while a frame is
    drawn, by holding a key or tapping it fast, drop them, and beep.
    """
    if event.type == pg.KEYUP:
        held_keys.discard(event.key)
        speaker.stop()
    if event.type != pg.KEYDOWN:
        return True
    released = event.key in held_keys and not pg.key.get_pressed()[event.key]
    held_keys.add(event.key)
    if pg.event.get(pg.KEYDOWN) and not released and event.key == pg.K_MINUS:
        speaker.start()
    else:
        speaker.stop()
    return not released


class Speaker:
    """The PC speaker."""

    def __init__(self) -> None:
        """Start silent."""
        self.channel: pg.mixer.Channel | None = None
        self.play_settings = PlaySettings()

    def start(self) -> None:
        """Start beeping."""
        if self.channel is None and (sound := square_wave()):
            self.channel = sound.play(loops=-1)

    def stop(self) -> None:
        """Stop beeping."""
        if self.channel is not None and pg.mixer.get_init():
            self.channel.stop()
        self.channel = None

    def play(self, tune: str) -> None:
        """Play a tune written in QBasic's PLAY notation."""
        sound, self.play_settings = tune_wave(tune, self.play_settings)
        if sound:
            sound.play()


def square_wave() -> pg.mixer.Sound | None:
    """Return a square wave that loops seamlessly.

    Each half wave is a whole number of samples, so the overtones that
    are too high for the sample rate fold back onto the beep's own
    overtones, instead of sounding like undertones. So, like the PC's
    timer chip, round the frequency to one that divides evenly into
    half the sample rate (the Nyquist frequency).
    """
    if (mixer := pg.mixer.get_init()) is None:
        return None
    rate, size, channels = mixer
    if size != -16:  # noqa: PLR2004
        return None
    half = max(1, round(rate / BEEP_FREQUENCY / 2))
    high, low = [BEEP_AMPLITUDE] * channels, [-BEEP_AMPLITUDE] * channels
    return pg.mixer.Sound(buffer=array("h", high * half + low * half))


NOTES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTALS = {"": 0, "#": 1, "+": 1, "-": -1}
ARTICULATIONS = {"MN": 7 / 8, "ML": 1, "MS": 3 / 4, "MF": None, "MB": None}
SETTINGS = {"T": "tempo", "L": "length", "O": "octave"}
PLAY_COMMAND = re.compile(r"\s*(M[NLSFB]|[<>]|[A-G][#+-]?|[LNOPT])(\d*)(\.*)\s*")


class PlaySettings(NamedTuple):
    """The settings that carry over from one PLAY statement to the next."""

    tempo: int = 120  # Quarter notes per minute
    length: int = 4  # Quarter notes
    octave: int = 4  # Octave 2 starts at middle C
    articulation: float = 7 / 8  # MN: sound 7/8 of each note


def notes(
    tune: str, settings: PlaySettings
) -> tuple[list[tuple[float, float, float]], PlaySettings]:
    """Return the frequency (0 for a rest), seconds, and articulation of each note."""
    result = []
    tune = tune.upper()
    pos = 0
    while pos < len(tune):
        if (match := PLAY_COMMAND.match(tune, pos)) is None:
            msg = f"Can't play {tune[pos:]!r}"
            raise ValueError(msg)
        pos = match.end()
        command, number, dots = match.groups()
        if command in ARTICULATIONS:
            articulation = ARTICULATIONS[command] or settings.articulation
            settings = settings._replace(articulation=articulation)
        elif command in "<>":
            octave = settings.octave + (1 if command == ">" else -1)
            settings = settings._replace(octave=octave)
        elif command in SETTINGS:
            settings = settings._replace(**{SETTINGS[command]: int(number)})
        else:
            # A note, N followed by a note number (N1 is the C of octave
            # 0, and N0 is a rest), or P followed by the length of a rest.
            if command == "N":
                key, number = int(number) - 1, ""
            elif command == "P":
                key = -1
            else:
                key = (
                    12 * settings.octave + NOTES[command[0]] + ACCIDENTALS[command[1:]]
                )
            frequency = 440 * 2 ** ((key - 33) / 12) if key >= 0 else 0
            beats = 4 / int(number or settings.length) * 1.5 ** len(dots)
            seconds = beats * 60 / settings.tempo
            result.append((frequency, seconds, settings.articulation))
    return result, settings


@cache
def tune_wave(
    tune: str, settings: PlaySettings
) -> tuple[pg.mixer.Sound | None, PlaySettings]:
    """Return the tune as square waves, and the settings it leaves behind.

    Each half wave is a whole number of samples, like in square_wave().
    """
    tune_notes, settings = notes(tune, settings)
    if (mixer := pg.mixer.get_init()) is None:
        return None, settings
    rate = mixer[0]
    samples = array("h")
    for frequency, seconds, articulation in tune_notes:
        length = round(rate * seconds)
        sounding = round(length * articulation) if frequency else 0
        if sounding:
            half = max(1, round(rate / frequency / 2))
            wave = [BEEP_AMPLITUDE] * half + [-BEEP_AMPLITUDE] * half
            samples.extend((wave * (sounding // len(wave) + 1))[:sounding])
        samples.extend([0] * (length - sounding))
    return pg.mixer.Sound(buffer=samples), settings


speaker = Speaker()
