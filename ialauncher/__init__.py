"""IA Launcher, a DOSBox frontend for the Internet Archive."""

import pygame as pg

if not getattr(pg, "IS_CE", False):
    msg = "IA Launcher requires pygame-ce, not pygame."
    raise ImportError(msg)
