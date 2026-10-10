import os, glob

from .dosbox import try_command


class ScummVMNotFound(Exception):
    pass


def get_scummvm_path():
    try:
        return try_command(['scummvm'])
    except:
        pass
    try:
        # Hardcoded path on macOS
        return try_command(['/Applications/ScummVM.app/Contents/MacOS/scummvm'])
    except:
        pass
    try:
        # Special case for Windows
        paths = []
        for var in ['ProgramFiles', 'ProgramFiles(x86)']:
            if pf := os.environ.get(var):
                paths.extend(glob.glob(f'{pf}\\scummvm*\\scummvm.exe'))
        return try_command([paths[0]])
    except:
        pass

    raise ScummVMNotFound("""

Uh-oh! The program ScummVM could not be found on your system. Some games in IA Launcher are played with ScummVM instead of DOSBox.

Please visit https://www.scummvm.org/ to learn more about ScummVM and download the correct installer for your operating system.

""")
