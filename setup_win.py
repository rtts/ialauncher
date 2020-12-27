'''
This is an alternative setup script which uses cx_Freeze to build a
Windows-native executable. Call it like this:

    C:\ialauncher>python setup_win.py build

This will generate a working application beneath the build/ directory.

I am still figuring out how to build an MSI installer, because the
command ``bdist_msi`` currently fails...

'''
import os
from cx_Freeze import setup, Executable

# Provide an executable that will run from the current directory:
with open('temp.py', 'w') as f:
    f.write('''
import multiprocessing
from ialauncher.main import main
if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
''')

setup(
    name='ialauncher',
    version = '2.1.0',
    description = 'A DOSBox frontend for the Internet Archive MS-DOS games collection',
    executables = [Executable('temp.py', targetName = 'ialauncher.exe')],
)

# Remove temporary executable
os.remove('temp.py')
