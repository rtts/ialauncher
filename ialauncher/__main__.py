"""Command-line entry point of IA Launcher."""

import argparse

from . import options
from .engine import run
from .scenes.loading import Loading


def main() -> None:
    """Parse the command-line arguments and start IA Launcher."""
    parser = argparse.ArgumentParser(
        description="DOSBox frontend for the Internet Archive MS-DOS games collection"
    )
    parser.add_argument(
        "--slideshow",
        type=int,
        metavar="X",
        help="Focus on a random title screen every X seconds",
    )
    parser.add_argument(
        "--fullscreen",
        action=argparse.BooleanOptionalAction,
        help="Start in fullscreen mode (default) or in a window",
    )
    parser.add_argument(
        "--slurp",
        dest="slurp",
        action="store_true",
        help=(
            "Slurp mode: downloads ALL games from the Internet Archive, one by "
            "one. This will take days to finish. Please don't do this for no "
            "reason; the Internet Archive has limited bandwidth. Also, consider "
            "donating first."
        ),
    )
    parser.add_argument(
        "--capture",
        dest="capture",
        action="store_true",
        help=(
            "Capture mode: lists all games without a title screen. While a game "
            "is running, each screenshot that appears in the captures directory "
            "is moved to its title.png."
        ),
    )
    parser.add_argument(
        "--captures-dir",
        metavar="DIR",
        help=(
            "Directory where DOSBox and ScummVM save screenshots "
            f"(default: {options.captures_dir})"
        ),
    )
    args = parser.parse_args()

    if args.fullscreen is not None:
        options.fullscreen = args.fullscreen
    if args.slideshow is not None:
        options.slideshow = args.slideshow
    if args.captures_dir is not None:
        options.captures_dir = args.captures_dir

    run(
        Loading(slurp=args.slurp, capture=args.capture),
        title="IA Launcher",
        fullscreen=options.fullscreen,
    )


if __name__ == "__main__":
    main()
