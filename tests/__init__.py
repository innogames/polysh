"""Polysh - Tests

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2024 InnoGames GmbH
"""
import pexpect
from pexpect.popen_spawn import PopenSpawn


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

def launch_polysh(args, input_data=None):
    args = ['uv', 'run', 'polysh'] + args

    if input_data is None:
        child = pexpect.spawn(args[0], args=args[1:], encoding='utf-8')
    else:
        child = PopenSpawn(args)
        child.send(input_data)
        child.sendeof()
    return child