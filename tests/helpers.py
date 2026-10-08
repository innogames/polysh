"""Polysh - Tests - Helpers

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


def expect_each(child, patterns):
    """Expect every pattern once, in whatever order they show up.

    The remote shells answer independently of each other and polysh prints
    their lines as they arrive, so two shells given the same command may
    report in either order."""
    pending = list(patterns)
    while pending:
        del pending[child.expect(pending)]
