#!/usr/bin/env python

import sys

sys.path.insert(0, 'setuptools-0.6c6-py2.4.egg')
from setuptools import setup, find_packages, command
from gsh.version import VERSION

# Monkey patch the install command so that it also installs the man page
# using the install_data command.
vanilla_install_run = command.install.install.run
def install_also_install_data(self):
    vanilla_install_run(self)
    self.run_command('install_data')

command.install.install.run = install_also_install_data

setup(name='gsh',
      version=VERSION,
      description='Group Shell',
      long_description=
'''gsh is used to launch several remote shells on many machines at the same
time and control them from a single command prompt.''',
      author='Guillaume Chazarain',
      author_email='guichaz@gmail.com',
      url='http://guichaz.free.fr/gsh',
      scripts=['bin/gsh'],
      data_files=[('share/man/man1', ['gsh.1'])],
      packages=find_packages(),
      license='GPL'
)
