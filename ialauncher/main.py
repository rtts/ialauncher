#!/usr/bin/env python3

import os, sys, random, argparse, subprocess
import games as gd
import pygame as pg
from .game import Game


def main():
    args = parse_args()
    check_dosbox()
    games = load_games()
    show_ui(games, args)


def parse_args():
    parser = argparse.ArgumentParser(description='DOSBox frontend for the Internet Archive MS-DOS games collection')
    parser.add_argument('--slideshow', type=int, metavar='X', help='Focus on a random title screen every X seconds')
    parser.add_argument('--fullscreen', action='store_true', help='Start in fullscreen mode')
    return parser.parse_args()


def check_dosbox():
    try:
        subprocess.run(['dosbox', '--version']).check_returncode()
    except:
        print("""
Uh-oh! The program DOSBox could not be found on your system.
IA Launcher acts as a frontend for DOSBox: when you select a game,
it starts DOSBox with the right arguments to play that game.

You can find more information and downloads on the DOSBox Wiki:

    https://www.dosbox.com/wiki/

You can verify that DOSBox is installed correctly by running the
following command:

    dosbox --version

Would you still like to start IA Launcher so you can see the games?
(Note: you won't be able to play them!)

[Y]es or [N]o: """, end='', flush=True)

        waiting = True
        while waiting:
            answer = input()
            if answer and answer in 'Yy':
                waiting = False
            elif answer and answer in 'Nn':
                sys.exit()
            else:
                print('Please answer [Y] or [N]: ', end='', flush=True)


def load_games():
    games = []
    print('Loading games', end='')
    games_dir = os.path.dirname(gd.__file__)
    for entry in os.listdir(games_dir):
        if not os.path.isdir(os.path.join(games_dir, entry)):
            continue
        if entry.startswith('.'):
            continue
        if entry.startswith('__'):
            continue
        try:
            games.append(Game(os.path.join(games_dir, entry)))
            print('.', end='', flush=True)
        except:
            raise ValueError('Unable to load', entry)
    print('')

    if not games:
        print('No games found!')
        sys.exit(1)

    games.sort()
    print(f'{len(games)} games loaded!')
    return games


def show_ui(games, args):
    pg.init()
    ADVANCE = pg.event.custom_type()
    pg.key.set_repeat(250, 25)
    if args.slideshow:
        pg.time.set_timer(ADVANCE, args.slideshow * 1000)
    info = pg.display.Info()
    size = info.current_w, info.current_h
    if args.fullscreen:
        # Note that SDL fullscreen is currently broken in Xmonad
        screen = pg.display.set_mode(size, flags=pg.FULLSCREEN)
    else:
        screen = pg.display.set_mode(size, flags=pg.RESIZABLE|pg.WINDOWMAXIMIZED)
    pg.display.set_caption('IA Launcher')
    current_game = random.randrange(len(games)) if args.slideshow else 0
    image = pg.image.load(games[current_game].get_titlescreen())
    scaled_image = image.copy()

    while event := pg.event.wait():
        if event.type == pg.QUIT:
            sys.exit()
        if event.type == ADVANCE:
            current_game = random.randrange(len(games))
            image = pg.image.load(games[current_game].get_titlescreen())
            scaled_image = image.copy()
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                sys.exit()
            elif event.key == pg.K_RIGHT:
                current_game = (current_game + 1) % len(games)
            elif event.key == pg.K_LEFT:
                current_game = (current_game - 1) % len(games)
            elif event.key == pg.K_SPACE:
                current_game = random.randrange(len(games))
            elif event.key == pg.K_RETURN:
                if event.mod & pg.KMOD_ALT:
                    games[current_game].start(autorun=False)
                else:
                    games[current_game].start()
                pg.event.clear()
            elif event.key == pg.K_DOWN:

                # Jump to the next game with different letter
                letter = games[current_game].identifier.lower()[0]
                for game in games[current_game:]:
                    if not game.identifier.lower().startswith(letter):
                        break
                    current_game += 1
                if current_game >= len(games):
                    current_game = 0

            elif event.key == pg.K_UP:

                # Jump to the first game that starts with previous game's letter
                letter = games[(current_game - 1) % len(games)].identifier.lower()[0]
                for i, game in enumerate(games):
                    if game.identifier.lower().startswith(letter):
                        current_game = i
                        break

            elif event.unicode:

                # Jump to specific letter
                for i, game in enumerate(games):
                    if game.identifier.lower().startswith(event.unicode):
                        current_game = i
                        break

            image = pg.image.load(games[current_game].get_titlescreen())
            scaled_image = image.copy()

        rect = screen.get_rect()
        if rect.size != scaled_image.get_rect().size:
            scaled_image = pg.transform.scale(image, rect.size)

        screen.blit(scaled_image, rect)
        pg.display.flip()
