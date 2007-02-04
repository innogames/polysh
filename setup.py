#!/usr/bin/env python

import sys

sys.path.append('setuptools-0.7a1dev_r53614-py2.4.egg')
from setuptools import setup, find_packages
from gsh.version import VERSION

setup(name='gsh',
      version=VERSION,
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
