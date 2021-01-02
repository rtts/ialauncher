import os
import random
import pygame as pg
import games as gd

from .game import Game
from .gamelist import GameList
from .framework import Scene
from . import options

ADVANCE = pg.event.custom_type()


class Loading(Scene):
    counter = 0

    def __init__(self):
        self.games_dir = os.path.dirname(gd.__file__)
        self.todo = [
            os.path.join(self.games_dir, entry) for entry in os.listdir(self.games_dir)
            if os.path.exists(os.path.join(self.games_dir, entry, 'metadata.ini'))
        ]
        self.games = GameList()
        super().__init__()

    def get_events(self):
        return pg.event.get()

    def handle(self, event):
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return self.done()

    def done(self):
        self.games.sort(slideshow=options.slideshow)
        return Browse(self.games)

    def update(self, screen):
        if not self.todo:
            return self.done()
        path = self.todo.pop()
        self.games.add(path)
        self.counter += 1
        screen.fill((0,0,0))
        draw(screen, f'''
Welcome to IA Launcher!
Found games directory at: {self.games_dir}
Loading games... {self.counter}
''')


class Browse(Scene):
    def __init__(self, games):
        self.games = games
        if options.slideshow:
            pg.time.set_timer(ADVANCE, options.slideshow * 1000)
        self.handlers = {
            pg.K_RIGHT: self.games.next_game,
            pg.K_LEFT: self.games.previous_game,
            pg.K_DOWN: self.games.next_letter,
            pg.K_UP: self.games.previous_letter,
            pg.K_SPACE: self.games.random_game,
        }
        super().__init__()

    def get_events(self):
        return [pg.event.wait()]

    def handle(self, event):
        if event.type == ADVANCE:
            self.games.random_game()
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
            if handler := self.handlers.get(event.key):
                handler()
            if event.unicode:
                self.games.letter(event.unicode)
            if event.key == pg.K_RETURN:
                game = self.games.get_current_game()
                if event.mod & pg.KMOD_SHIFT:
                    game.reset()
                if not game.is_ready():
                    Download(game).run(self.screen)
                if game.is_ready():

                    # Start playing (spawns a new thread)
                    game.start(autorun=not event.mod & pg.KMOD_ALT)

    def update(self, screen):
        image = self.games.get_image()
        rect = screen.get_rect()
        scaled_image = pg.transform.scale(image, rect.size)
        screen.blit(scaled_image, rect)


class Download(Scene):
    def __init__(self, game):
        self.game = game
        super().__init__()

        # Start downloading (spawns a new thread)
        self.game.download()

    def handle(self, event):
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False

    def update(self, screen):
        if self.game.download_completed():
            return False
        self.screen.fill((0,0,0))
        draw(screen, f'Downloading {self.game.urls[0]} ({self.game.get_size():.1f} MB)')


def draw(surface, text, margin=15, font_size=24, line_height=1.25, font_family='monospace', color=(255,255,255)):
    '''
    Simple text drawing routine, adapted from
    https://www.pygame.org/wiki/TextWrap

    '''
    font = pg.font.SysFont(font_family, font_size)
    rect = surface.get_rect()
    ypos = margin
    yinc = int(line_height * font_size)

    for line in text.split('\n'):
        if ypos + yinc > rect.bottom:
            break
        while line:
            i = 0

            # Determine maximum width of line
            while font.size(line[:i])[0] + 2*margin < rect.width and i < len(line):
                i += 1

            # Render the line and blit it to the surface
            image = font.render(line[:i], True, color)
            surface.blit(image, (margin, ypos))
            ypos += yinc

            # Remove the text we just blitted
            line = line[i:]

