import os, sys, glob, subprocess

def try_path(path):
    subprocess.run([path, '--version'], capture_output=True).check_returncode()
    return path

def get_dosbox_path():
    try:
        return try_path('dosbox')
    except:
        pass
    try:
        # Special case for macOS
        return try_path('/Applications/dosbox.app/Contents/MacOS/DOSBox')
    except:
        pass
    try:
        # Special case for Windows
        pf = os.environ['ProgramFiles(x86)']
        path = glob.glob(f'{pf}\dosbox*\dosbox.exe')[0]
        return try_path(path)
    except:
        pass

    print("""
Uh-oh! The program DOSBox could not be found on your system.
IA Launcher acts as a frontend for DOSBox: when you select a game,
it starts DOSBox with the right arguments to play that game.

Please visit https://www.dosbox.com/ to learn more about DOSBox and
download the correct installer for your operating system.
""")
    input("Press any key to exit...")
    sys.exit(1)
