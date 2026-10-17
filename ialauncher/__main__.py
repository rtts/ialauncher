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
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.fullscreen is not None:
        options.fullscreen = args.fullscreen
    if args.slideshow is not None:
        options.slideshow = args.slideshow

    run(
        Loading(slurp=args.slurp),
        title="IA Launcher",
        fullscreen=options.fullscreen,
    )


if __name__ == "__main__":
    main()
