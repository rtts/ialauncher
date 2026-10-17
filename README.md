IA Launcher
===========

**A DOSBox frontend for the [Internet Archive MS-DOS games
collection](https://archive.org/details/softwarelibrary_msdos_games)**

IA Launcher is a graphical games launcher for all those gorgeous
MS-DOS games from yestermillenium. It uses the Internet Archive to
download games on-the-fly and DOSBox to play them offline. Visit the
[IA Launcher website](https://ialauncher.created.today/games.htm) for
a list of all the included games.

**Hurrah! IA Launcher now has its own Windows installer! You can
download it [here](https://rtts.eu/ialauncher-3.0.0-amd64.msi).**

You can also install IA Launcher using `pip3 install ialauncher` on
any operating system. Continue reading for detailed instructions.

![Screenshot of IA Launcher](https://i.imgur.com/WQhGrQy.jpg)


Features
--------

- Batteries included! Thousands of games playable out-of-the-box.
- Graphical user interface for quickly browsing through title screens.
- Seamlessly downloads games from a curated library of game URLs.
- Custom startup logic for all included games.
- Saves state such as savegames and settings for each game.


Installation
------------

First of all, get yourself a snazzy retro-looking PC. Or just use your
current computer running your operating system of choice. Start by
installing the following dependencies:

- [Python](https://www.python.org/) version 3.12 or higher
- [DOSBox](https://www.dosbox.com/) version 0.74 or higher

*Note from the future: DOSBox is getting a bit long in the tooth (the
last release was in 2019) so you may want to look into using a more
modern alternative such as [DOSBox
Staging](https://www.dosbox-staging.org/). It should be a drop-in
replacement!*

Now you can install IA Launcher using `pip`. Open a command-line
window and type the following command:

    pip3 install ialauncher

You can now launch the interface using the `ialauncher` command. To
see the available options, type `ialauncher --help`.


Special Keys
------------

- Space: start slideshow
- Arrow keys: navigate through the games list
- A-Z: start searching
- Enter: launch the selected game
- Shift-Enter: reset game state before starting game
  (warning: you will lose your save files!)
- Alt-Enter: open DOSBox without starting the game
  (useful for debugging, see "Troubleshooting" below)
- Minus: zoom out
- Plus: zoom in
- Esc: quit

*Tip: try some of your favorite cheat codes. They might just work!*

During gameplay, you should also be familiar with the [DOSBox Special
Keys](https://www.dosbox.com/wiki/Special_Keys). The most important
key is `Ctrl-F9`, which immediately exits DOSBox and returns to IA
Launcher.


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
- Use the `dir` command to see which files are present.
- Use the `cd` command to change to the game subdirectory, if needed.
- Look for a file named `install.{bat,exe,com}`,
  `setsound.{bat,exe,com}` or `setup.{bat,exe,com}` and execute it.

Hopefully, the setup utility will allow you to change the sound card
parameters. For starters, try these values:

Sound card: Sound Blaster 16 and/or AdLib\
Address/port: 220\
IRQ: 7\
DMA: 1


### Help, my game doesn't run at all!

Each game's metadata, including the command that starts the game, is
stored in the game's `metadata.ini` file. In many cases IA Launcher
provides the needed commands to install and set up the game when run
for the first time. However, in other cases the commands listed in
`metadata.ini` assume the installation was already done with default
settings. In these cases, try the following:

- Press Alt-Enter to start DOSBox with the game directory mounted as
  the `C:` drive.
- Type `dosbox.bat` and press Enter. This attempts to start the game.
- Type `type dosbox.bat` to see how IA Launcher attempts to start the game.
- (Optional) Type `mount a .` to mount the game's directory as the
  floppy drive, because many games assume they are being installed
  from a floppy disk.
- (Optional) Type `a:` to switch to the mounted floppy drive.
- Type `install` and follow the installation procedure, accepting all
  the default values.

After the installation has finished, try launching the game again and
hopefully the default startup command will now work. If not, keep
reading...


### Help! The default startup command is incorrect!

Here is how you can change the command(s) that launch a game. Read
carefully, this will be on the exam:

- Press Alt-Enter to start DOSBox with the game directory mounted as
  the `C:` drive.
- (Optional) Type `echo cd [directoryname] > dosbox.bat` to put the
  `cd` command in the file named `dosbox.bat`.
- Type `echo [command that launches the game] >> dosbox.bat` to append
  the command that launches the game to the file `dosbox.bat`.
- Execute `dosbox.bat` and verify that your game now launches correctly.

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

If you used Git to clone this repository, you will notice that the
previous steps will leave unstaged changes in your working tree. You
are encouraged to create a pull request for those changes, so together
we can make IA Launcher even better!
