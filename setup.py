#!/usr/bin/env python

from distutils.core import setup
from gsh.version import VERSION

setup(name='gsh',
      version=VERSION,
      description='Group Shell',
      long_description=
"""gsh is used to launch several remote shells on many machines at the same
time and control them from a single command prompt.""",
      author='Guillaume Chazarain',
      author_email='guichaz@gmail.com',
      url='http://guichaz.free.fr/gsh',
      scripts=['bin/gsh'],
      data_files=[('share/man/man1', ['gsh.1'])],
      packages=['gsh'],
      license='GPL'
)
