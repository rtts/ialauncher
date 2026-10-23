"""Basic Input/Output System."""

from array import array

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

    def start(self) -> None:
        """Start beeping."""
        if self.channel is None and (sound := square_wave()):
            self.channel = sound.play(loops=-1)

    def stop(self) -> None:
        """Stop beeping."""
        if self.channel is not None and pg.mixer.get_init():
            self.channel.stop()
        self.channel = None


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


speaker = Speaker()
