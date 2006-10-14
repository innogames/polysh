import cmd
import sys
import termios

from gsh.console import set_stdin_blocking

# The controlling shell, accessible with Ctrl-C
singleton = None

def make_singleton(options):
    global singleton
    singleton = control_shell(options)

def launch():
    return singleton.launch()

class control_shell(cmd.Cmd):
    """The little command line brought when a SIGINT is received"""
    def __init__(self, options):
        cmd.Cmd.__init__(self)
        self.options = options

    def launch(self):
        self.stop = False
        set_stdin_blocking(True)
        intro = sys.argv[0] + ' command line'
        while True:
            try:
                cmd.Cmd.cmdloop(self, intro)
            except KeyboardInterrupt:
                pass
            else:
                return
        set_stdin_blocking(False)

    # We do this just to have 'help' in the 'Documented commands'
    def do_help(self, command):
        """List available commands"""
        return cmd.Cmd.do_help(self, command)

    def do_list(self, command):
        """List all remote shells and their states"""
        from gsh import remote_dispatcher
        nr_active = nr_dead = 0
        instances = []
        for i in remote_dispatcher.all_instances():
            instances.append(i.get_info())
            if i.active:
                nr_active += 1
            else:
                nr_dead += 1
        remote_dispatcher.format_info(instances)
        print '%s\n\n%d active shells, %d dead shells, total: %d' % \
               ('\n'.join(instances), nr_active, nr_dead, nr_active + nr_dead)

    def do_continue(self, command):
        """Go back to gsh"""
        self.stop = True

    def do_EOF(self, command):
        """Go back to gsh"""
        return self.do_continue(command)

    def do_quit(self, command):
        """Quit gsh"""
        sys.exit(0)

    def do_get_print_first(self, command):
        """Check whether we only print the first line for each command output"""
        print 'print_first = ' + str(not not self.options.print_first)

    def do_set_print_first(self, command):
        """Print only the first line for each command output"""
        self.options.print_first = True

    def do_unset_print_first(self, command):
        """Print all lines for each command output"""
        self.options.print_first = False

    def do_send_sigint(self, command):
        """Send a Ctrl-C to all remote shells"""
        from gsh import remote_dispatcher
        for i in remote_dispatcher.all_instances():
            c = termios.tcgetattr(i.fd)[6][termios.VINTR]
            i.dispatch_write(c)

    def do_send_eof(self, command):
        """Send a Ctrl-D to all remote shells"""
        from gsh import remote_dispatcher
        for i in remote_dispatcher.all_instances():
            c = termios.tcgetattr(i.fd)[6][termios.VEOF]
            i.dispatch_write(c)

    def postcmd(self, stop, line):
        return self.stop

    def emptyline(self):
        pass
