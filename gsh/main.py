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
# Copyright (c) 2006 Guillaume Chazarain <guichaz@yahoo.fr>

# Requires python 2.4

import asyncore
import atexit
import locale
import optparse
import os
import signal
import sys

from gsh import remote_dispatcher
from gsh.console import show_status, watch_window_size
from gsh import control_shell
from gsh.stdin import the_stdin_thread

def kill_all():
    """When gsh quits, we kill all the remote shells we started"""
    for i in remote_dispatcher.all_instances():
        os.kill(i.pid, signal.SIGKILL)

def parse_cmdline():
    usage = '%s [OPTIONS] HOSTS...' % (sys.argv[0])
    parser = optparse.OptionParser(usage)
    try:
        parser.add_option('--log-dir', type='str', dest='log_dir',
                          help='directory to log each machine conversation' +
                                                                      ' [none]')
    except optparse.OptionError:
        # Starting with python-2.4 'str' is recognized as an alias to 'string',
        # so we use this to check the python version
        print >> sys.stderr, 'Your python version is too old (%s)' % \
                                                        (sys.version.split()[0])
        print >> sys.stderr, 'You need at least Python 2.4'
        sys.exit(1)
    parser.add_option('--command', type='str', dest='command', default=None,
                      help='command to execute on the remote shells',
                      metavar='CMD')
    parser.add_option('--ssh-exec', type='str', dest='ssh_exec', default=None,
                      help='path to the ssh command [ssh]', metavar='FILE')
    parser.add_option('--ssh-shell-cmd', type='str', dest='ssh_shell_cmd',
                      default=None, help='shell command used to launch ssh',
                      metavar='CMD')
    parser.add_option('--print-first', action='store_true', dest='print_first',
                      help='print first line [by default all lines]')
    parser.add_option('--abort-errors', action='store_true', dest='abort_error',
                      help='abort if hosts are failing [by default ignore]')
    parser.add_option('--debug', action='store_true', dest='debug',
                      help='fill the logs with debug informations')

    options, args = parser.parse_args()
    if not args:
        parser.error('no hosts given')

    if options.ssh_exec and options.ssh_shell:
        parser.error('--ssh-exec and --ssh-shell-cmd are mutually exclusive')

    return options, args

def main_loop():
    while True:
        try:
            while True:
                completed, total = remote_dispatcher.count_completed_processes()
                if not the_stdin_thread.ready_event.isSet():
                    show_status(completed, total)
                if completed and completed == total:
                    the_stdin_thread.ready_event.set()
                if remote_dispatcher.all_terminated():
                    raise asyncore.ExitNow
                asyncore.loop(count=1)
        except KeyboardInterrupt:
            control_shell.launch()
        except asyncore.ExitNow:
            sys.exit(0)
        else:
            sys.exit(1)

def main():
    """Launch gsh"""
    locale.setlocale(locale.LC_ALL, '')
    options, args = parse_cmdline()
    control_shell.make_singleton(options)

    if options.log_dir:
        try:
            os.mkdir(options.log_dir)
        except OSError:
            pass # The dir already exists

    the_stdin_thread.activate(not options.command)

    atexit.register(kill_all)
    for host in args:
        remote_dispatcher.remote_dispatcher(options, host)

    watch_window_size()
    main_loop()
