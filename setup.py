#!/usr/bin/env python

import os
from setuptools import setup, find_packages

setup(name='gsh',
      version='0.1',
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
