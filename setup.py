#!/usr/bin/env python3
import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name = 'ialauncher',
    version = '2.2.1',
    author = 'Jaap Joris Vens',
    author_email = 'jj+ialauncher@rtts.eu',
    description = 'A DOSBox frontend for the Internet Archive',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = 'https://ialauncher.created.today/',
    packages = setuptools.find_packages(),
    entry_points = {
        'console_scripts': ['ialauncher=ialauncher.__main__:main'],
    },
    include_package_data = True,
    classifiers = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent',
    ],
    python_requires = '>=3.8',
    install_requires = [
        'pygame',
    ],
)
