import os
import random
import pygame as pg
import games as gd

from .gamelist import GameList, SEARCH_TIMEOUT
from .engine import Scene
from . import options

ADVANCE = pg.event.custom_type()
SEARCH_EXPIRED = pg.event.custom_type()


class Loading(Scene):
    counter = 0

    def __init__(self, slurp_mode=False):
        self.slurp_mode = slurp_mode
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

    def load_games(self, number_of_games):
        while self.todo and number_of_games:
            path = self.todo.pop()
            self.games.add(path)
            self.counter += 1
            number_of_games -= 1

    def download_game(self):
        path = self.todo.pop()
        self.games.add(path)
        Download(self.games.games[-1]).run(self.screen)
        self.counter += 1

    def done(self):
        self.games.sort(slideshow=options.slideshow)
        return Browse(self.games)

    def update(self, screen):
        if not self.todo:
            return self.done()
        if self.slurp_mode:
            self.download_game()
        else:
            self.load_games(10)
        screen.fill((0,0,0))
        self.draw(screen, f'''
Welcome to IA Launcher!
Found games directory at: {self.games_dir}
Loading games... {self.counter}
''')


class Browse(Scene):
    def __init__(self, games):
        self.games = games
        self.slideshow = options.slideshow
        self.set_slideshow(bool(options.slideshow))
        self.handlers = {
            pg.K_RIGHT: self.games.next_game,
            pg.K_LEFT: self.games.previous_game,
            pg.K_DOWN: self.games.next_letter,
            pg.K_UP: self.games.previous_letter,
            pg.K_SPACE: self.games.random_game,
        }
        super().__init__()

    def set_slideshow(self, enabled: bool) -> None:
        pg.time.set_timer(ADVANCE, self.slideshow * 1000 if enabled else 0)

    def get_events(self):
        return [pg.event.wait()]

    def handle(self, event):
        if event.type == ADVANCE:
            self.games.reset_search()
            self.games.random_game()
        if event.type == SEARCH_EXPIRED:
            self.games.reset_search()
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
            if event.key != pg.K_SPACE:
                self.set_slideshow(False)
            elif not self.games.is_searching():
                self.set_slideshow(True)
            if event.key == pg.K_SPACE and self.games.is_searching():
                self.games.search(' ')
            elif event.key == pg.K_BACKSPACE:
                self.games.backspace()
            elif handler := self.handlers.get(event.key):
                self.games.reset_search()
                handler()
            elif event.unicode.isprintable() and event.unicode:
                self.games.search(event.unicode)

            # (Re)start the timer that removes the query from the screen
            if self.games.query:
                pg.time.set_timer(SEARCH_EXPIRED, SEARCH_TIMEOUT, loops=1)
            if event.key == pg.K_RETURN:
                self.games.reset_search()
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
        if self.games.query:
            self.draw_query(screen)

    def draw_query(self, screen, margin=15, padding=8):
        if not hasattr(self, 'font'):
            self.font = pg.font.SysFont('monospace', 24)
        image = self.font.render(self.games.query, True, (255,255,255))
        rect = image.get_rect().inflate(2*padding, 2*padding)
        rect.topleft = (margin, margin)
        screen.fill((0,0,0), rect)
        screen.blit(image, image.get_rect(center=rect.center))


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
        screen.fill((0,0,0))
        self.draw(screen, f'Downloading {self.game.urls[0]} ({self.game.get_size():.1f} MB)')
