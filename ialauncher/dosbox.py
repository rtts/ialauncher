import os, sys, glob, subprocess

def get_dosbox_path():
    try:
        subprocess.run(['dosbox', '--version'], capture_output=True).check_returncode()
        return 'dosbox'
    except:
        pass
    try:
        pf = os.environ['ProgramFiles(x86)']
        path = glob.glob(f'{pf}\dosbox*\dosbox.exe')[0]
        subprocess.run([path, '--version'], capture_output=True).check_returncode()
        return path
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
