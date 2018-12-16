IALAUNCHER - Internet Archive games Launcher
============================================

Play all of the Internet Archive's MS-DOS games offline!
--------------------------------------------------------

IA Launcher is a graphical games launcher for all those georgeous
MS-DOS games from yestermillenium. It uses the [Internet
Archive](https://archive.org/) to download games on-the-fly
and [DOSBox](https://www.dosbox.com/) to play them.

IA Launcher currently runs on GNU/Linux operating systems but should
easily be portable to other platforms.

Features:
---------

- Batteries included!
- Thousands of games playable out-of-the-box
- Beautiful title screens
- Easily add your own games
- Automatically downloads game data from archive.org
- Saves state such as savegames and settings for each game
- "Edit mode" lets you hide/unhide games and update title screens
- Oldschool MIDI background music

Installation
------------

First of all, get yourself a snazzy retro looking PC. Then, install
the following dependencies:

- [DOSBox](https://www.dosbox.com/) (on Debian-based systems: `apt
  install dosbox`)
- [Timidity++](http://timidity.sourceforge.net/) (`apt install
  timidity`)
- WebKit2 (`apt install gir1.2-webkit2-4.0`)
- Python3 (`apt install python3`)

Finally, use pip to install the Python dependencies:

    pip3 install -r requirements.txt

Launch the interface using the `ialauncher` command. To see the
available options, type `ialauncher --help`

Background music
----------------

If Timidity++ is installed, the interface will play MIDI files from
the `collections/midi` directory in random order.

[VGMusic](https://www.vgmusic.com/) is an excellent source to find
original game soundtracks in MIDI format. I recommend running `wget -r
-np https://www.vgmusic.com/music/computer/microsoft/windows/` to
populate the `midi` directory.

Special Keys
------------

- Arrow keys: navigate through the games list
- Enter: launch the selected game
- A-Z: Jump to the first game that starts with the letter A-Z
- Plus key: increase grid size
- Minus key: decrease grid size
- Dot/greater than key: play next MIDI song
- Delete: hides the selected game (only in edit mode)
- F2: rename the selected game (only in edit mode)

During gameplay, you should also be familiar with the [DOSBox Special
Keys](https://www.dosbox.com/wiki/Special_Keys)
