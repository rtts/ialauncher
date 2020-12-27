#!/usr/bin/env python3

import os, sys, random, argparse
import games as gd

from .game import Game


def main():
    args = parse_args()
    games = load_games()
    show_ui(games, args)


def parse_args():
    parser = argparse.ArgumentParser(description='DOSBox frontend for the Internet Archive MS-DOS games collection')
    parser.add_argument('--slideshow', type=int, metavar='X', help='Focus on a random title screen every X seconds')
    parser.add_argument('--no-fullscreen', dest='fullscreen', action='store_false', help='Don’t start in fullscreen mode')
    return parser.parse_args()


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
    import pygame as pg
    pg.init()
    ADVANCE = pg.event.custom_type()
    pg.key.set_repeat(250, 25)
    if args.slideshow:
        pg.time.set_timer(ADVANCE, args.slideshow * 1000)
    size = 640, 480
    if args.fullscreen:
        # Note that SDL fullscreen is currently broken in Xmonad
        screen = pg.display.set_mode(size, flags=pg.FULLSCREEN)
    else:
        screen = pg.display.set_mode(size, flags=pg.RESIZABLE)
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
