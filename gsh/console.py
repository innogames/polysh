import fcntl
import os
import sys

# We remember the length of the prompt in order
# to clear it with as many ' ' characters
prompt_length = 0

def set_stdin_blocking(blocking):
    """asyncore sets stdin to O_NONBLOCK, stdout/err may be duped to stdin
    so they may be set to O_NONBLOCK too. We have to clear this flag when
    printing to the console as we prefer blocking rather than having an
    exception when the console is busy"""
    stdin_fd = sys.stdin.fileno()
    flags = fcntl.fcntl(stdin_fd, fcntl.F_GETFL)
    if blocking:
        flags = flags & ~os.O_NONBLOCK
    else:
        flags = flags | os.O_NONBLOCK
    fcntl.fcntl(stdin_fd, fcntl.F_SETFL, flags)

def console_output(msg, output=sys.stdout):
    """Use instead of print, to prepare the console (clear the prompt) and
    restore it after"""
    set_stdin_blocking(True)
    global prompt_length
    print >> output, '\r', prompt_length * ' ', '\r', msg,
    prompt_length = 0
    set_stdin_blocking(False)

def show_prompt():
    """The prompt is '[available shells/alive shells]'"""
    from gsh import remote_dispatcher
    completed, total = remote_dispatcher.count_completed_processes()
    prompt = '\r[%d/%d]> ' % (completed, total)
    console_output(prompt)
    global prompt_length
    prompt_length = max(prompt_length, len(prompt))
    set_stdin_blocking(True)
    # We flush because there is no '\n' but a '\r'
    sys.stdout.flush()
    set_stdin_blocking(False)
