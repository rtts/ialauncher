#!/usr/bin/env python3

import os
import subprocess
import sys
from jinja2 import Template

output = subprocess.run(
    ['git', 'ls-tree', '-d', '--name-only', '-z', 'main', 'games/'],
    capture_output=True, text=True, check=True,
).stdout
games = sorted((os.path.basename(path) for path in output.split('\0') if path), key=str.lower)

with open('games.htm.template', newline='') as f:
    template = Template(f.read(), newline_sequence='\r\n', keep_trailing_newline=True)

with open('games.htm', 'w', newline='') as f:
    f.write(template.render(games=games))
