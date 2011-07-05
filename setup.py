#!/usr/bin/env python

from distutils.core import setup
from polysh.version import VERSION

setup(name='polysh',
      version=VERSION,
      description='Polysh',
      long_description=
"""polysh is used to launch several remote shells on many machines at the same
time and control them from a single command prompt.""",
      author='Guillaume Chazarain',
      author_email='guichaz@gmail.com',
      url='http://guichaz.free.fr/polysh',
      scripts=['bin/polysh'],
      data_files=[('share/man/man1', ['polysh.1'])],
      packages=['polysh'],
      license='GPL'
)
