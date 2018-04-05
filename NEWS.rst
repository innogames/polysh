Unreleased
    * Drop :upload and :replicate file transfer features.
    * No longer forward Ctrl-Z sent to gsh are forwaded to the remote shells.
    * Save and restore polysh history from ~/.polysh_hisory.


Version 0.4
    * Renamed to polysh.
    * Added a --user option to specify the remote user to login as.
    * New file transfer code that does not assume additional connectivity
      between the host running gsh and the remote shells but still assumes
      connectivity between the remote shells.
    * Added an option to disable colorized hostnames.


Version 0.3.1
    * If the :{en|dis}able command would have no effect, it changes all other
      shells to the inverse enable value.
    * Consistently add a space between the shell name and the colon to ease
      parsing
      the output.
    * The gsh exit code is aggregated from all remote shells taking the max.
    * :export_rank has been renamed to :export_vars as it now also exports the
      hostname.
    * Added a --password-file to login using a password.
    * The file transfer feature now works even if the gsh source is in a ZIP
      file.
    * Migrated from setuptools to distutils.
    * Hostnames are now colorized in the output.


Version 0.3
    * Removed --log-dir=LOG_DIR option as it is less useful than expected
    * Added a --log-file=LOG_FILE option aggregating all remote shells
    * Removed --quick-sh as it is now the default
    * Replaced the control shell with colon prefixed commands
    * The prompt uses readline even when not all remote shells are ready
    * Ctrl-C, Ctrl-D and Ctrl-Z sent to gsh are forwaded to the remote shells
    * Shell commands prefixed by an exclamation mark are run locally
    * Added the :chdir control command to change the local directory
    * Added the :hide_password control command, to use with su(1) for example
    * Added the :reset_prompt control command, for use when launching a shell
    * Added the :replicate and :upload control commands to do some file
      transfer
    * Added the :export_rank control command to uniquely identify each shell
    * Added the :show_read_buffer control command to see what gsh just read
    * Common SSH key problems are detected and some help is printed
    * New completion from the local filesystem
    * Simplified :list output, and added the last printed line


Version 0.2
    * Using readline to provide fancy command line edition and completion from
      history
    * Incomplete lines are printed after some delay
    * Remote shells can be dynamically added/deleted/renamed
    * New option --quick-sh to avoid launching a full blown session
    * Added hostname expansion: for example host<1-100> and host<001-100>
    * Added an option to read hostnames from a file
    * Removed useless option to print only the first line of output
    * Misc. bug fixes and optimizations
    * Added a man page

Version 0.1
    * First release
