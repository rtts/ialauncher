#!/usr/bin/env python3

import os
import games
from jinja2 import Template
from ialauncher.game import Game

gamesdir = os.path.dirname(games.__file__)
games = []
for path in os.listdir(gamesdir):
    try:
        game = Game(os.path.join(gamesdir, path))
        game.configure()
        games.append(game)
    except:
        pass
games.sort()
with open('games.htm.template') as f:
    template = Template(f.read())

print(template.render(games=games))
