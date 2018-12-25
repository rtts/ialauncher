Internet Archive Launcher for MS-DOS games
==========================================

Play all of the Internet Archive's MS-DOS games offline!
--------------------------------------------------------

![Screenshot of IA Launcher](https://i.imgur.com/WQhGrQy.jpg)

IA Launcher is a graphical games launcher for all those georgeous
MS-DOS games from yestermillenium. It uses the [Internet
Archive](https://archive.org/) to download games on-the-fly
and [DOSBox](https://www.dosbox.com/) to play them.

IA Launcher currently runs on GNU/Linux operating systems but should
easily be portable to other platforms.


Features:
---------

- Batteries included! Thousands of games playable out-of-the-box
- Graphical user interface showing the title screens of all games
- Easily add new games to the list (if you do, send me a pull request!)
- Automatically downloads game data from archive.org
- Saves state such as savegames and settings for each game


Installation
------------

First of all, get yourself a snazzy retro looking PC. Then, install
the following dependencies:

- [DOSBox](https://www.dosbox.com/) (on Debian-based systems: `apt
  install dosbox`)
- WebKit2 (`apt install gir1.2-webkit2-4.0`)
- Python3 (`apt install python3`)

Then install the `ialauncher` Python package:

    git clone https://github.com/rtts/ialauncher
    cd ialauncher
    pip3 install .

Finally, copy or symlink the `games` directory to your home directory
i.e. `~/games`. (If you now a better way of including the games as
package data, please let me know!)

You can now launch the interface using the `ialauncher` command. To
see the available options, type `ialauncher --help`


Special Keys
------------

- Arrow keys: navigate through the games list
- Enter: launch the selected game
- Alt-Enter: open DOSBox without starting the game
  (usefull for debugging, see "Troubleshooting" below)
- A-Z: Jump to the first game that starts with the letter A-Z
- Plus key: increase grid size
- Minus key: decrease grid size
- Esc key: exit

During gameplay, you should also be familiar with the [DOSBox Special
Keys](https://www.dosbox.com/wiki/Special_Keys)


Troubleshooting
---------------

### Help, my game doesn't run correctly / has no sound!

Welcome to the world of MS-DOS where you are constantly fighting with
IRQ values, memory managers and setup programs. Thankfully, the
default DOSBox configuration runs nearly all DOS games perfectly out
of the box. Also, all the games in the `games` directory have custom
DOSBox configurations (where needed) and startup commands in their
`metadata.ini` files. However, you will certainly end up in situations
where you have to reconfigure a game. Try the following:

- Press Alt-Enter to start DOSBox with the game directory mounted as
  the `C:` drive.
- Use the `dir` command to see which files are present
- Use the `cd` command to change to the game subdirectory, if needed
- Look for a file named `install.{bat,exe,com}`,
  `setsound.{bat,exe,com}` or `setup.{bat,exe,com}` and execute it

Hopefully, the setup utility will allow you to change the sound card
parameters. DOSBox emulates all kinds of sounds cards, so try the
following and it will probably work:

Sound card: Soundblaster or AdLib\
Address/port: 220\
IRQ: 7\
DMA: 1


### Help, my game doesn't run at all!

Each game's metadata, including the command that starts the game, is
stored in a file called `metadata.ini`. In many cases IA Launcher
provides the needed commands to install and setup the game when run
for the first time. However, in other cases the commands listed in
`metadata.ini` simply assume the installation was already done with
default settings. In these cases, try the following:

- Press Alt-Enter to start DOSBox with the game directory mounted as
  the `C:` drive.
- Type `mount a .` to mount the game's directory as the floppy drive
  (many games assume they are being installed from a floppy disk)
- Type `a:` to switch to the mounted floppy drive
- Type `install` and follow the installation procedure, accepting all
  the default values

After the installation has finished, try launching the game again and
hopefully the default startup command will now work. If not, keep
reading...


### Help! The default startup command is incorrect!

Here is how you can easily change the command(s) that launch a game:

- Press Alt-Enter to start DOSBox with the game directory mounted as
  the `C:` drive.
- (optionally:) Type `echo cd [directoryname] > dosbox.bat` to put the
  `cd` command in the file named `dosbox.bat`
- Type `echo [command that launches the game] >> dosbox.bat` to append
  the command that launches the game to the file `dosbox.bat`
- Execute `dosbox.bat` and verify that your game now launches correctly

When you exit the emulator, IA Launcher will save the contents of
`dosbox.bat` to the `emulator_start` variable inside the game's
`metadata.ini`. The next time you launch the game, the `dosbox.bat`
file will be run automatically.

More advanced logic can be created with batch file syntax. As an
example, here is the contents of `emulator_start` for the game SimCity
2000:

    if exist sc2000 goto run
    mount a .
    a:
    install
    :run
    cd sc2000
    sc2000

You can also [mount CD images](https://www.dosbox.com/wiki/MOUNT) and
get CD audio while playing:

    imgmount d Quake.cue -t iso
    if exist quake goto run
    d:
    install
    :run
    cd quake
    quake

Did you get a previously not-working game running by changing the
`emulator_start` variable? Or did you add a new game and captured a
nice title screen? Please send me a pull request!
