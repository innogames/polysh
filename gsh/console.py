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

def set_blocking_stdin(blocking):
    """stdin and stdout may be dup(2)ed streams. So when we print to
    stdout, we have to ensure stdin is in non-blocking mode"""
    global stdin_is_blocking_counter
    flags = fcntl.fcntl(0, fcntl.F_GETFL, 0)
    if blocking:
        stdin_is_blocking_counter += 1
        if stdin_is_blocking_counter == 1:
            flags = flags & ~os.O_NONBLOCK
    else:
        stdin_is_blocking_counter -= 1
        if stdin_is_blocking_counter == 0:
            flags = flags | os.O_NONBLOCK
    fcntl.fcntl(0, fcntl.F_SETFL, flags)


# We remember the status in order
# to clear it with as many ' ' characters
last_status = None

def console_output(msg, output=sys.stdout):
    """Use instead of print, to clear the status information before printing"""
    global last_status
    if last_status:
        status_length = len(last_status)
    else:
        status_length = 0
    set_blocking_stdin(True)
    try:
        print >> output, '\r', status_length * ' ', '\r', msg,
    finally:
        set_blocking_stdin(False)
    last_status = None

def show_status(completed, total):
    """The status is '[available shells/alive shells]'"""
    status = '\r[%d/%d]> ' % (completed, total)
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
