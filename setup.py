#!/usr/bin/env python3
"""Polysh - Setup Script

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2018 InnoGames GmbH
"""
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from setuptools import setup
from os import path
from sys import exit, version_info as PYTHON_VERSION
from polysh import VERSION as POLYSH_VERSION

if PYTHON_VERSION < (3, 5):
    print('Aborting polysh installation! Polysh requires python 3.5 or later.')
    exit(1)

# Get the long description from the README file
here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst')) as file:
    long_description = file.read()

setup(
    name='polysh',
    version='.'.join(str(d) for d in POLYSH_VERSION),
    description='Control thousands of ssh sesions from a single prompt',
    long_description=long_description,
    url='http://github.com/innogames/polysh/',
    maintainer='InnoGames System Administration',
    maintainer_email='it@innogames.com',

    keywords='gsh group shell cluster ssh multiplexer',
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        'Intended Audience :: System Administrators',
        'Intended Audience :: Developers',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Shells',
        'Topic :: System :: Clustering',
        'Topic :: System :: Distributed Computing',

        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',

        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Development Status :: 5 - Production/Stable',

        # This does not influence pip when choosing what to install. It is used
        # for the package list on the pypi website.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.5',

    packages=['polysh'],
    entry_points={
        'console_scripts': [
            'polysh=polysh.main:main',
        ],
    },
)
