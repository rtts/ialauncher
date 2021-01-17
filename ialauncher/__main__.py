import argparse

from .engine import Main
from .scenes import Loading
from . import options


def main():
    parser = argparse.ArgumentParser(description='DOSBox frontend for the Internet Archive MS-DOS games collection')
    parser.add_argument('--slideshow', type=int, metavar='X', help='Focus on a random title screen every X seconds')
    parser.add_argument('--fullscreen', dest='fullscreen', action='store_true', help='Start in fullscreen mode (default)')
    parser.add_argument('--no-fullscreen', dest='no_fullscreen', action='store_true', help='Don’t start in fullscreen mode')
    parser.add_argument('--slurp-mode', dest='slurp_mode', action='store_true', help='Slurp mode: downloads ALL games from the Internet Archive, one by one. This will take days to finish. Please don’t do this for no reason; the Internet Archive has limited bandwith. Also, consider donating first.')
    args = parser.parse_args()

    if args.fullscreen ^ args.no_fullscreen:
        options.fullscreen = args.fullscreen or not args.no_fullscreen
    options.slideshow = args.slideshow or options.slideshow

    Main(Loading(slurp_mode=args.slurp_mode), title='IA Launcher', fullscreen=options.fullscreen)


if __name__ == '__main__':
    main()
