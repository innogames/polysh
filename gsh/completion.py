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
# Copyright (c) 2008 Guillaume Chazarain <guichaz@yahoo.fr>

import readline

# All the words that have been typed in gsh. Used by the completion mechanism.
history_words = set()

# When listing possible completions, the complete() function is called with
# an increasing state parameter until it returns None. Cache the completion
# list instead of regenerating it for each completion item.
completion_results = None

def complete(text, state):
    """On tab press, return the next possible completion"""
    from gsh.control_commands_helpers import complete_control_command
    global completion_results
    if state == 0:
        line = readline.get_line_buffer()
        if line.startswith(':'):
            # Control command completion
            completion_results = complete_control_command(line, text)
        else:
            # Main shell completion from history
            l = len(text)
            completion_results = [w + ' ' for w in history_words if len(w) > l \
                                                         and w.startswith(text)]
    if state < len(completion_results):
        return completion_results[state]
    completion_results = None

def add_to_history(cmd):
    words = [w for w in cmd.split() if len(w) > 1]
    history_words.update(words)
    if len(history_words) > 10000:
        del history_words[:-10000]

def remove_last_history_item():
    """The user just typed a password..."""
    last = readline.get_current_history_length() - 1
    readline.remove_history_item(last)

def install_completion_handler():
    readline.set_completer(complete)
    readline.parse_and_bind('tab: complete')
    readline.set_completer_delims(' \t\n')

