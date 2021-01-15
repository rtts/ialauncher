'''
This is a _very_ simple engine for building pygame games. There
are two classes: Main and Scene. The latter one is meant to be
subclassed by your own custom scenes. Example usage:

    class Intro(Scene):
        def __init__(self):
            self.image = pg.image.load('my_awesome_title_screen.png')
            super().__init__()

        def handle(self, event):
            if event.type == pg.KEYDOWN:
                 return LevelOne()

        def update(self, screen):
            screen.blit(self.image, (0,0))

    if __name__ == '__main__':
        scene = Intro()
        Main(scene, title='My awesome game')

'''
import pygame as pg


class Main:
    '''
    Initialize pygame and start the game using the given scene.

    '''

    def __init__(self, scene, title='Game', fullscreen=True):
        pg.init()
        pg.key.set_repeat(250, 25)
        pg.mouse.set_visible(False)
        pg.display.set_caption(title)

        if fullscreen:
            info = pg.display.Info()
            size = info.current_w, info.current_h
            screen = pg.display.set_mode(size, flags=pg.FULLSCREEN)
        else:
            size = 640, 480
            screen = pg.display.set_mode(size, flags=pg.RESIZABLE)

        while scene:
            pg.event.clear()
            scene = scene.run(screen)


class Scene:
    '''
    Base class for scenes. Subclasses are meant to override the
    handle() and update() methods.

    '''

    def __init__(self):
        self.clock = pg.time.Clock()

    def handle(self, event):
        raise NotImplementedError()

    def update(self, screen):
        raise NotImplementedError()

    def get_events(self):
        self.clock.tick(60)
        return pg.event.get()

    def run(self, screen):
        '''
        Run this scene's main event loop. Return either the next scene or
        None, at which point Main ends.

        '''
        self.screen = screen
        next_scene = None
        while next_scene is None:
            next_scene = self.update(screen)
            pg.display.flip()
            for event in self.get_events():
                if event.type == pg.QUIT:
                    return
                next_scene = self.handle(event)

        return next_scene

    def draw(self, surface, text, margin=15, font_size=24, line_height=1.25, font_family='monospace', color=(255,255,255)):
        '''
        Simple text drawing routine, adapted from
        https://www.pygame.org/wiki/TextWrap

        '''
        if not hasattr(self, 'font'):
            self.font = pg.font.SysFont(font_family, font_size)
        rect = surface.get_rect()
        ypos = margin
        yinc = int(line_height * font_size)

        for line in text.split('\n'):
            if ypos + yinc > rect.bottom:
                break
            while line:
                i = 0

                # Determine maximum width of line
                while self.font.size(line[:i])[0] + 2*margin < rect.width and i < len(line):
                    i += 1

                # Render the line and blit it to the surface
                image = self.font.render(line[:i], True, color)
                surface.blit(image, (margin, ypos))
                ypos += yinc

                # Remove the text we just blitted
                line = line[i:]
