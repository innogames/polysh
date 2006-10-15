# Requires python 2.4

import asyncore
import atexit
import locale
import optparse
import os
import signal
import sys

from gsh import remote_dispatcher
from gsh.console import show_prompt, watch_window_size
from gsh import control_shell
from gsh.stdin_reader import stdin_reader

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
    parser.add_option('--ssh', type='str', dest='ssh', default='ssh',
                      help='ssh command to use [ssh]')
    parser.add_option('--print-first', action='store_true', dest='print_first',
                      help='print first line [by default all lines]')
    parser.add_option('--abort-errors', action='store_true', dest='abort_error',
                      help='abort if hosts are failing [by default ignore]')
    parser.add_option('--debug', action='store_true', dest='debug',
                      help='fill the logs with debug informations')

    options, args = parser.parse_args()
    if not args:
        parser.error('no hosts given')
    return options, args

def main_loop():
    while True:
        try:
            while True:
                if remote_dispatcher.all_terminated():
                    raise asyncore.ExitNow
                show_prompt()
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
    stdin_reader(options)

    if options.log_dir:
        try:
            os.mkdir(options.log_dir)
        except OSError:
            pass # The dir already exists

    atexit.register(kill_all)
    for host in args:
        remote_dispatcher.remote_dispatcher(options, host)

    watch_window_size()
    main_loop()
