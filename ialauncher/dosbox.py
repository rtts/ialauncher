import os, glob, subprocess


class DOSBoxNotFound(Exception):
    pass


def try_command(command):
    subprocess.run(command + ['--version'], capture_output=True).check_returncode()
    return command


def get_dosbox_path():
    try:
        return try_command(['dosbox'])
    except:
        pass
    try:
        # Proper way to do it on macOS
        return try_command(['open', '-a', 'DOSBox', '--args'])
    except:
        pass
    try:
        # Fallback to hardcoded path on macOS
        return try_command(['/Applications/dosbox.app/Contents/MacOS/DOSBox'])
    except:
        pass
    try:
        # Special case for Windows
        pf = os.environ['ProgramFiles(x86)']
        path = glob.glob(f'{pf}\dosbox*\dosbox.exe')[0]
        return try_command([path])
    except:
        pass

    raise DOSBoxNotFound("""

Uh-oh! The program DOSBox could not be found on your system. IA Launcher acts as a frontend for DOSBox: when you select a game, it starts DOSBox with the right arguments to play that game.

Please visit https://www.dosbox.com/ to learn more about DOSBox and download the correct installer for your operating system.

""")
