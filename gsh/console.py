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

import errno
import sys

# We remember the last printed status in order to clear it with ' ' characters
last_status = None

stdout_is_terminal = sys.stdout.isatty()

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

def console_output(msg, output=sys.stdout):
    """Use instead of print, to clear the status information before printing"""
    if stdout_is_terminal:
        global last_status
        if last_status:
            safe_write(output, '\r' + len(last_status) * ' ' + '\r')
            last_status = None
    safe_write(output, msg)

def show_status(completed, total):
    """The status is '[available shells/alive shells]>'"""
    if stdout_is_terminal:
        status = 'waiting [%d/%d]> ' % (completed, total)
        console_output(status)
        global last_status
        last_status = status
        # We flush because there is no '\n'
        sys.stdout.flush()
