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
# Copyright (c) 2006, 2007 Guillaume Chazarain <guichaz@yahoo.fr>

import fcntl
import signal
import struct
import sys
import termios

from gsh.terminal_size import terminal_size

# We remember the last printed status in order to clear it with ' ' characters
last_status = None

stdout_is_terminal = sys.stdout.isatty()

def console_output(msg, output=sys.stdout):
    """Use instead of print, to clear the status information before printing"""
    if stdout_is_terminal:
        global last_status
        if last_status:
            output.write('\r' + len(last_status) * ' ' + '\r')
            last_status = None
    output.write(msg)

def show_status(completed, total):
    """The status is '[available shells/alive shells]>'"""
    if stdout_is_terminal:
        status = 'waiting [%d/%d]> ' % (completed, total)
        console_output(status)
        global last_status
        last_status = status
        # We flush because there is no '\n'
        sys.stdout.flush()

def watch_window_size():
    """Detect when the window size changes, and propagate the new size to the
    remote shells"""
    def sigwinch(unused_signum, unused_frame):
        from gsh import remote_dispatcher
        h, w = terminal_size()
        # python bug http://python.org/sf/1112949 on amd64
        # from ajaxterm.py
        bug = struct.unpack('i', struct.pack('I', termios.TIOCSWINSZ))[0]
        packed_size = struct.pack('HHHH', w, h, 0, 0)
        for i in remote_dispatcher.all_instances():
            if i.enabled:
                fcntl.ioctl(i.fd, bug, packed_size)
    sigwinch(None, None)
    signal.signal(signal.SIGWINCH, sigwinch)
