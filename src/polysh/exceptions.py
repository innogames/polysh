"""Polysh - Exceptions

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2024 InnoGames GmbH
"""
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class ExitNow(Exception):
    """Exception to signal clean exit. First argument is exit code."""
    pass


class QuitAsked(BaseException):
    """Raised in the main thread when the user pressed Ctrl-\\, letting
    it kill the process so that the user has a way to quit polysh.

    SIGINT arrives as KeyboardInterrupt for free (and it's passed through
    to the remote shell), SIGQUIT does not, so the handler raises this to reach
    the same place in the main loop."""
    pass
