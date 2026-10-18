#!/usr/bin/env python3

import os
import re
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

with open('index.htm', newline='') as f:
    index = f.read()

with open('index.htm', 'w', newline='') as f:
    f.write(re.sub(r'[\d,]+ games</A>', f'{len(games):,} games</A>', index))
