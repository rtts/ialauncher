"""Tests for IA Launcher, run with `python -m unittest`.

The environment is set up here, before any test module imports pygame.
"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
