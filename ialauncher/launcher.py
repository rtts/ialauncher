import pygame as pg

from .state import Initializing

class IALauncher:
    def launch(args):
        pg.init()
        pg.key.set_repeat(250, 25)
        pg.mouse.set_visible(False)
        info = pg.display.Info()
        size = info.current_w, info.current_h
        if args.fullscreen:
            # Note that SDL fullscreen is currently broken in Xmonad
            screen = pg.display.set_mode(size, flags=pg.FULLSCREEN)
        else:
            screen = pg.display.set_mode((640,480), flags=pg.RESIZABLE)
        pg.display.set_caption('IA Launcher')
        state = Initializing(screen, args.slideshow)
        while state:
            pg.event.clear()
            state = state.event_loop()
