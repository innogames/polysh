"""Polysh - Tab Completion

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2018 InnoGames GmbH
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

import glob
import os
import readline
from typing import Optional, List, Set

from polysh.control_commands_helpers import complete_control_command
from polysh.control_commands_helpers import expand_local_path


def complete_local_path(path: str) -> List[str]:
    def get_suffix(p: str) -> str:
        if os.path.isdir(p):
            return '/'
        return ''
    path = expand_local_path(path)
    paths = [p + get_suffix(p) for p in glob.glob(path + '*')]
    return paths


def remove_dupes(words: List[str]) -> List[str]:
    added = set()  # type: Set[str]
    results = list()
    for w in words:
        stripped = w.rstrip('/ ')
        if stripped not in added:
            added.add(stripped)
            results.append(w)
    return results


def read_commands_in_path() -> List[str]:
    commands = set()  # type: Set[str]

    for path in (os.getenv('PATH') or '').split(':'):
        if path:
            try:
                listing = os.listdir(path)
            except OSError:
                pass
            else:
                commands |= set(listing)
    return list(commands)


# All the words that have been typed in polysh. Used by the completion
# mechanism.
history_words = set()  # type: Set[str]

# When listing possible completions, the complete() function is called with
# an increasing state parameter until it returns None. Cache the completion
# list instead of regenerating it for each completion item.
completion_results = None

# Commands in $PATH, used for the completion of the first word
user_commands_in_path = read_commands_in_path()


def complete(text: str, state: int) -> Optional[str]:
    """On tab press, return the next possible completion"""
    global completion_results
    if state == 0:
        line = readline.get_line_buffer()
        if line.startswith(':'):
            # Control command completion
            completion_results = complete_control_command(line, text)
        else:
            if line.startswith('!') and text and line.startswith(text):
                dropped_exclam = True
                text = text[1:]
            else:
                dropped_exclam = False
            completion_results = []
            # Complete local paths
            completion_results += complete_local_path(text)
            # Complete from history
            l = len(text)
            completion_results += [w + ' ' for w in history_words if
                                   len(w) > l and w.startswith(text)]
            if readline.get_begidx() == 0:
                # Completing first word from $PATH
                completion_results += [w + ' ' for w in user_commands_in_path
                                           if len(w) > l and w.startswith(text)]
            completion_results = remove_dupes(completion_results)
            if dropped_exclam:
                completion_results = ['!' + r for r in completion_results]

    if state < len(completion_results):
        return completion_results[state]
    completion_results = None
    return None


def add_to_history(cmd: str) -> None:
    if len(history_words) < 10000:
        history_words.update(w for w in cmd.split() if len(w) > 1)


def remove_last_history_item() -> None:
    """The user just typed a password..."""
    last = readline.get_current_history_length() - 1
    readline.remove_history_item(last)


def install_completion_handler() -> None:
    readline.set_completer(complete)
    readline.parse_and_bind('tab: complete')
    readline.set_completer_delims(' \t\n')
