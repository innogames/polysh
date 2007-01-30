#!/usr/bin/env python

import os
import sys

sys.path.append('setuptools-0.6c5-py2.4.egg')
from setuptools import setup, find_packages

news_file = file('NEWS')
version = news_file.readline().strip()

setup(name='gsh',
      version=version,
      description='Group Shell',
      long_description=
'''gsh is used to launch several remote shells on many machines at the same
time and control them from a single command prompt.''',
      author='Guillaume Chazarain',
      author_email='guichaz@yahoo.fr',
      url='http://guichaz.free.fr/gsh',
      scripts=['bin/gsh'],
      packages=find_packages(),
      license='GPL'
)
