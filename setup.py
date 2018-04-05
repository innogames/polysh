#!/usr/bin/env python3

from setuptools import setup

from polysh import VERSION

setup(
    name='polysh',
    version='.'.join(map(str, VERSION)),
    maintainer='InnoGames System Administration',
    maintainer_email='it@innogames.com',
    url='https://github.com/innogames/polysh',
    data_files=[('share/man/man1', ['polysh.1'])],
    packages=['polysh'],
    long_description=(
        'polysh is used to launch several remote shells on many machines at'
        ' the same time and control them from a single command prompt.'),
    entry_points={
        'console_scripts': [
            'polysh=polysh.main:main',
        ],
    },
    license='GPL'
)
