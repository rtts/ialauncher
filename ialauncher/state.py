import os
import random
import pygame as pg
import games as gd

from .game import Game
from .gamelist import GameList

ADVANCE = pg.event.custom_type()


class State:
    '''Just a quick explanation of states:

    Each state is actually it's own complete "game", with its own
    event loop. The "Initializing" state, for instance, updates its
    screen every time a new game is loaded. The "Browsing" state,
    however, only updates when it receives an event. This is contrary
    to typical pygame event loops which update the screen a fixed
    numbers of times per second.

    These event loops are run like this by the IALauncher class:

        while state:
            state = state.event_loop()

    So, any time, a state can decide to quit its event loop and return
    a new state. Most states accept a previous state as init argument,
    so they can return to it when needed.

    '''

    def __init__(self, screen):
        self.screen = screen

    def handle(self, event):
        if event.type == pg.QUIT:
            return False
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            return False
        return True


class Initializing(State):
    counter = 0

    def __init__(self, screen, slideshow=0):
        self.screen = screen
        self.slideshow = slideshow
        self.games_dir = os.path.dirname(gd.__file__)
        self.todo = [
            os.path.join(self.games_dir, entry) for entry in os.listdir(self.games_dir)
            if os.path.exists(os.path.join(self.games_dir, entry, 'metadata.ini'))
        ]
        self.games = GameList(slideshow)

    def event_loop(self):
        running = True
        while running:
            for event in pg.event.get():
                running = self.handle(event)

            if self.todo:
                path = self.todo.pop()
                self.games.add(path)
                self.counter += 1
            else:
                running = False

            self.render()
            pg.display.flip()

        # Done! Move on to next state
        self.games.sort()
        return Browsing(self)

    def render(self):
        self.screen.fill((0,0,0))
        line = 0
        size = 32
        font = pg.font.SysFont('monospace', size)
        for message in [
                'Welcome to IA Launcher!',
                f'Found games directory at: {self.games_dir}',
                f'Loading games... {self.counter}',
        ]:
            res = font.render(str(message), False, (255,255,255), (0,0,0))
            self.screen.blit(res, (0,line))
            line += size


class Browsing(State):
    def __init__(self, previous_state):
        self.previous_state = previous_state
        self.screen = previous_state.screen
        self.games = previous_state.games
        self.autorun = True
        if previous_state.slideshow:
            pg.time.set_timer(ADVANCE, previous_state.slideshow * 1000)
        self.handlers = {
            pg.K_RIGHT: self.games.next_game,
            pg.K_LEFT: self.games.previous_game,
            pg.K_DOWN: self.games.next_letter,
            pg.K_UP: self.games.previous_letter,
            pg.K_SPACE: self.games.random_game,
        }
        self.next_state = None

    def event_loop(self):
        running = True
        while running:
            self.render()
            pg.display.flip()
            running = self.handle(pg.event.wait())

        return self.next_state

    def render(self):
        image = self.games.get_image()
        rect = self.screen.get_rect()
        scaled_image = pg.transform.scale(image, rect.size)
        self.screen.blit(scaled_image, rect)

    def handle(self, event):
        if event.type == ADVANCE:
            self.games.random_game()
        if event.type == pg.KEYDOWN:
            handler = self.handlers.get(event.key)
            if handler: handler()
            if event.unicode:
                self.games.letter(event.unicode)
            if event.key == pg.K_RETURN:
                # Alt-Enter starts DOSBox without starting the game
                # Shift-Enter forces redownloading the game
                game = self.games.get_current_game()
                game.autorun = not event.mod & pg.KMOD_ALT
                if event.mod & pg.KMOD_SHIFT:
                    game.reset()
                if game.is_ready():
                    self.next_state = Playing(self, game)
                else:
                    self.next_state = Downloading(self, game)
                return False

        return super().handle(event)


class Downloading(State):
    def __init__(self, previous_state, game):
        self.screen = previous_state.screen
        self.previous_state = previous_state
        self.game = game

        # Start downloading (spawns a new process)
        self.game.download()

    def event_loop(self):
        running = True
        while running:
            self.render()
            pg.display.flip()
            pg.time.wait(50)
            for event in pg.event.get():
                running = self.handle(event)
            if self.game.download_completed():
                return Playing(self.previous_state, self.game)

    def render(self):
        self.screen.fill((0,0,0))
        line = 0
        size = 32
        font = pg.font.SysFont('monospace', size)
        rect = self.screen.get_rect()
        drawText(self.screen, f'Downloading {self.game.urls[0]} ({self.game.get_size():.1f} MB)', (255,255,255), rect, font)


class Playing(State):
    def __init__(self, previous_state, game):
        self.previous_state = previous_state
        game.start()

    def event_loop(self):
        # As you can see, the multiple-state-machinery is starting to
        # break down...
        self.previous_state.next_state = None
        return self.previous_state


def drawText(surface, text, color, rect, font, aa=False, bkg=None):
    rect = pg.Rect(rect)
    y = rect.top
    lineSpacing = -2

    # get the height of the font
    fontHeight = font.size("Tg")[1]

    while text:
        i = 0

        # determine if the row of text will be outside our area
        if y + fontHeight > rect.bottom:
            break

        # determine maximum width of line
        while font.size(text[:i])[0] < rect.width and i < len(text):
            i += 1

        # render the line and blit it to the surface
        if bkg:
            image = font.render(text[:i], 1, color, bkg)
            image.set_colorkey(bkg)
        else:
            image = font.render(text[:i], aa, color)

        surface.blit(image, (rect.left, y))
        y += fontHeight + lineSpacing

        # remove the text we just blitted
        text = text[i:]

    return text
