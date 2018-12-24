#!/usr/bin/env python3
import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name = 'ialauncher',
    version = '1.0',
    author = 'Jaap Joris Vens',
    author_email = 'jj@rtts.eu',
    description = 'Play all of the Internet Archive’s MS-DOS games offline!',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = 'https://github.com/rtts/ialauncher',
    packages = setuptools.find_packages(),
    scripts = ['bin/ialauncher'],
    package_data = {
        'ialauncher': ['*.html'],
    },
    classifiers = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent', # except for the hardcoded ~/games path...
    ],
    install_requires = [
        'jinja2',
        'PyGObject',
        'natsort',
    ],
)
