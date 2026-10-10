import os
import random
import shutil
import pygame as pg
import games as gd

from .gamelist import GameList, SEARCH_TIMEOUT
from .engine import Scene
from . import options

ADVANCE = pg.event.custom_type()
SEARCH_EXPIRED = pg.event.custom_type()


class Loading(Scene):
    counter = 0

    def __init__(self, slurp_mode=False, capture_mode=False):
        self.slurp_mode = slurp_mode
        self.capture_mode = capture_mode
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
        Download(self.games.games[-1], unzip=False).run(self.screen)
        self.counter += 1

    def done(self):
        self.games.sort(slideshow=options.slideshow)
        if self.capture_mode:
            return Capture(self.games)
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


class Capture(Scene):
    '''
    List all games without a title screen. While a game is running,
    watch the captures directory and move every new screenshot to the
    title.png of that game.

    '''
    POLL_INTERVAL = 500

    def __init__(self, games):
        self.games = [game for game in games.games if not game.get_titlescreen()]
        self.current = 0
        self.offset = 0
        self.captured = set()
        self.running = None
        self.captures_dir = os.path.expanduser(options.captures_dir)
        self.last_poll = 0
        self.preview = None
        super().__init__()

    def handle(self, event):
        if event.type != pg.KEYDOWN:
            return
        if event.key == pg.K_ESCAPE:
            return False
        moves = {
            pg.K_DOWN: 1,
            pg.K_UP: -1,
            pg.K_PAGEDOWN: 20,
            pg.K_PAGEUP: -20,
            pg.K_END: len(self.games),
            pg.K_HOME: -len(self.games),
        }
        if event.key in moves and self.games:
            self.current = max(0, min(len(self.games) - 1, self.current + moves[event.key]))
            self.preview = None
        if event.key == pg.K_RETURN and self.games and not self.running:
            game = self.games[self.current]
            if event.mod & pg.KMOD_SHIFT:
                game.reset()
            if not game.is_ready():
                Download(game).run(self.screen)
            if game.is_ready():
                self.watch(game)

                # Start playing (spawns a new thread)
                game.start(autorun=not event.mod & pg.KMOD_ALT)

    def watch(self, game):
        os.makedirs(self.captures_dir, exist_ok=True)
        self.running = game
        self.existing = set(os.listdir(self.captures_dir))
        self.sizes = {}

    def poll(self):
        '''
        Move new screenshots to the title screen of the running game,
        but only once their size has stopped changing.

        '''
        for name in sorted(os.listdir(self.captures_dir)):
            path = os.path.join(self.captures_dir, name)
            if name in self.existing or not name.lower().endswith('.png'):
                continue
            size = os.path.getsize(path)
            if size and self.sizes.get(name) == size:
                dest = os.path.join(self.running.path, 'title.png')
                shutil.copyfile(path, dest)
                os.remove(path)
                print(f'Captured {name} as title screen of {self.running.identifier}')
                self.captured.add(self.running)
                self.preview = None
                del self.sizes[name]
            else:
                self.sizes[name] = size

    def update(self, screen):
        if self.running and pg.time.get_ticks() - self.last_poll >= self.POLL_INTERVAL:
            self.last_poll = pg.time.get_ticks()
            running = self.running.is_running()
            self.poll()
            if not running:
                self.running = None

        screen.fill((0,0,0))
        if not hasattr(self, 'font'):
            self.font = pg.font.SysFont('monospace', 24)
        rect = screen.get_rect()
        margin = 15
        line_height = self.font.get_linesize()

        status = f'Running: {self.running.identifier}' if self.running else 'Enter: play, Alt-Enter: play without autorun, Esc: quit'
        header = f'{len(self.captured)} of {len(self.games)} captured | {status}'
        screen.blit(self.font.render(header, True, (255,255,0)), (margin, margin))

        # Game list on the left half, scrolled to keep the selection visible
        top = margin + 2 * line_height
        rows = max(1, (rect.height - top - margin) // line_height)
        if self.current < self.offset:
            self.offset = self.current
        elif self.current >= self.offset + rows:
            self.offset = self.current - rows + 1
        list_width = rect.width // 2 - 2 * margin
        for i, game in enumerate(self.games[self.offset:self.offset + rows], self.offset):
            mark = '*' if game in self.captured else ' '
            color = (0,0,0) if i == self.current else (255,255,255)
            y = top + (i - self.offset) * line_height
            if i == self.current:
                screen.fill((255,255,255), (margin, y, list_width, line_height))
            text = self.font.render(f'{mark} {game.identifier}', True, color)
            screen.blit(text, (margin, y), (0, 0, list_width, line_height))

        # Preview of the captured title screen on the right half
        if self.games and (path := self.games[self.current].get_titlescreen()):
            if self.preview is None:
                self.preview = pg.image.load(path)
            area = pg.Rect(rect.width // 2, top, rect.width // 2 - margin, rect.height - top - margin)
            w, h = self.preview.get_size()
            scale = min(area.width / w, area.height / h)
            image = pg.transform.scale(self.preview, (int(w * scale), int(h * scale)))
            screen.blit(image, image.get_rect(midtop=area.midtop))


class Download(Scene):
    def __init__(self, game, unzip: bool = True):
        self.game = game
        super().__init__()

        # Start downloading (spawns a new thread)
        self.game.download(unzip)

    def handle(self, event):
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False

    def update(self, screen):
        if self.game.download_completed():
            return False
        screen.fill((0,0,0))
        self.draw(screen, self.game.download_thread.status)
