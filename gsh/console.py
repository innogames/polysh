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

import fcntl
import os
import signal
import struct
import sys
import termios

from gsh.terminal_size import terminal_size

stdin_is_blocking_counter = 0
stdin_blocking_flags = fcntl.fcntl(0, fcntl.F_GETFL, 0) & ~os.O_NONBLOCK
stdin_nonblocking_flags = fcntl.fcntl(0, fcntl.F_GETFL, 0) | os.O_NONBLOCK

def set_blocking_stdin(blocking):
    """stdin and stdout may be dup(2)ed streams. So when we print to
    stdout, we have to ensure stdin is in non-blocking mode"""
    global stdin_is_blocking_counter
    new_flags = None
    if blocking:
        stdin_is_blocking_counter += 1
        if stdin_is_blocking_counter == 1:
            new_flags = stdin_blocking_flags
    else:
        stdin_is_blocking_counter -= 1
        if stdin_is_blocking_counter == 0:
            new_flags = stdin_nonblocking_flags
    if new_flags is not None:
        fcntl.fcntl(0, fcntl.F_SETFL, new_flags)


# We remember the last printed status in order to clear it with ' ' characters
last_status = None

stdout_is_terminal = sys.stdout.isatty()

def console_output(msg, output=sys.stdout):
    """Use instead of print, to clear the status information before printing"""
    if stdout_is_terminal:
        global last_status
        if last_status:
            status_length = len(last_status)
        else:
            status_length = 0
    set_blocking_stdin(True)
    try:
        if stdout_is_terminal:
            print >> output, '\r', status_length * ' ', '\r', msg,
        else:
            print >> output, msg,
    finally:
        set_blocking_stdin(False)
    if stdout_is_terminal:
        last_status = None

def show_status(completed, total):
    """The status is '[available shells/alive shells]>'"""
    if stdout_is_terminal:
        status = '[%d/%d]> ' % (completed, total)
        global last_status
        if last_status != status:
            console_output(status)
            last_status = status
            set_blocking_stdin(True)
            try:
                # We flush because there is no '\n' but a '\r'
                sys.stdout.flush()
            finally:
                set_blocking_stdin(False)

def watch_window_size():
    """Detect when the window size changes, and propagate the new size to the
    remote shells"""
    def sigwinch(unused_signum, unused_frame):
        from gsh import remote_dispatcher
        set_blocking_stdin(True)
        try:
            h, w = terminal_size()
            # python bug http://python.org/sf/1112949 on amd64
            # from ajaxterm.py
            bug = struct.unpack('i', struct.pack('I', termios.TIOCSWINSZ))[0]
            packed_size = struct.pack('HHHH', w, h, 0, 0)
            for i in remote_dispatcher.all_instances():
                if i.enabled:
                    fcntl.ioctl(i.fd, bug, packed_size)
        finally:
            set_blocking_stdin(False)
    sigwinch(None, None)
    signal.signal(signal.SIGWINCH, sigwinch)
