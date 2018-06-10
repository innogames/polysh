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


# Make sure we have a recent setuptools version otherwise the installation will
# fail anyway.
from pkg_resources import parse_version
from setuptools import setup, __version__

if parse_version(__version__) < parse_version('39.2.0'):
    from sys import exit
    print(
        'Aborting polysh installation! Please upgrade your setuptools first: ',
        '"pip3 install setuptools pip --upgrade"')
    exit(1)

setup()
