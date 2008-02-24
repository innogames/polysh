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
# Copyright (c) 2006, 2007, 2008 Guillaume Chazarain <guichaz@gmail.com>

import errno
import sys

# We remember the length of the last printed status in order to
# clear it with ' ' characters
last_status_length = None

def safe_write(output, buf):
    """We can get a SIGWINCH when printing, which will cause write to raise
    an EINTR. That's not a reason to stop printing."""
    while True:
        try:
            output.write(buf)
            break
        except IOError, e:
            if e.errno != errno.EINTR:
                raise

def console_output(msg):
    """Use instead of print, to clear the status information before printing"""
    from gsh.remote_dispatcher import options
    if options.interactive:
        from gsh.stdin import the_stdin_thread
        the_stdin_thread.no_raw_input()
        global last_status_length
        if last_status_length:
            safe_write(sys.stdout, '\r' + last_status_length * ' ' + '\r')
            last_status_length = 0
    safe_write(sys.stdout, msg)

def set_last_status_length(length):
    """The length of the prefix to be cleared when printing something"""
    global last_status_length
    last_status_length = length

