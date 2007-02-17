#!/usr/bin/env python
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# See the COPYING file for license information.
#
# Copyright (c) 2007 Guillaume Chazarain <guichaz@yahoo.fr>

import os
import unittest
import sys
import optparse
import pexpect

import coverage

ALL_TESTS = unittest.TestSuite()

def import_tests():
    py_files = [p for p in os.listdir('tests') if p.endswith('.py')]
    tests = list(set([p[:p.index('.')] for p in py_files]))
    for name in tests:
        module = getattr(__import__('tests.' + name), name)
        for test in module.TESTS:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(test)
            ALL_TESTS.addTest(suite)

def parse_cmdline():
    parser = optparse.OptionParser()
    parser.add_option('--coverage', '-c', action='store_true', dest='coverage',
                      default=False, help='include coverage tests')
    options, args = parser.parse_args()
    if args:
        parser.error()
    return options

def remove_coverage_files():
    for filename in os.listdir('.'):
        if filename.startswith('.coverage'):
            os.remove(filename)

def end_coverage():
    coverage.the_coverage.start()
    coverage.the_coverage.collect()
    coverage.the_coverage.stop()
    modules = [p[:-3] for p in os.listdir('../gsh') if p.endswith('.py')]
    coverage.report(['../gsh/%s.py' % (m) for m in modules])
    remove_coverage_files()
    # Prevent the atexit.register(the_coverage.save) from recreating the files
    coverage.the_coverage.usecache = coverage.the_coverage.cache = None

def main():
    options = parse_cmdline()
    if options.coverage:
        remove_coverage_files()
    import_tests()
    try:        
        unittest.main(argv=[sys.argv[0], '-v'], defaultTest='ALL_TESTS')
    finally:
        if options.coverage:
            end_coverage()

def launch_gsh(arg):
    prefix = '../gsh.py'
    if parse_cmdline().coverage:
        prefix = './coverage.py -x -p ' + prefix
    return pexpect.spawn(prefix + ' ' + arg, timeout=5)

if __name__ == '__main__':
    main()
