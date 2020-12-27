import argparse

from .launcher import IALauncher


def main():
    args = parse_args()
    IALauncher.launch(args)


def parse_args():
    parser = argparse.ArgumentParser(description='DOSBox frontend for the Internet Archive MS-DOS games collection')
    parser.add_argument('--slideshow', type=int, metavar='X', help='Focus on a random title screen every X seconds')
    parser.add_argument('--no-fullscreen', dest='fullscreen', action='store_false', help='Don’t start in fullscreen mode')
    return parser.parse_args()
