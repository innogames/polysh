Version 0.1
    * First release

Version 0.2
    * Use readline to provide fancy command line edition and completion from
      history
    * Print incomplete lines after some delay
    * Support dynamically adding/deleting/renaming remote shells
    * New option `--quick-sh` to avoid launching a full blown session
    * Add hostname expansion: for example `host<1-100>` and `host<001-100>`
    * Add an option to read hostnames from a file
    * Remove useless option to print only the first line of output
    * Miscellaneous bug fixes and optimizations
    * Add man page

Version 0.3
    * Remove `--log-dir=LOG_DIR` option as it is less useful than expected
    * Add `--log-file=LOG_FILE` option aggregating all remote shells
    * Remove `--quick-sh` as it is now the default
    * Replace the control shell with colon prefixed commands
    * Make the prompt use readline even when not all remote shells are ready
    * Forward `Ctrl-C`, `Ctrl-D` and `Ctrl-Z` to the remote shells
    * Allow running local commands
    * Add `:chdir` control command to change the local directory
    * Add `:hide_password` control command, to use with `su(1)` for example
    * Add `:reset_prompt` control command, for use when launching a shell
    * Add `:replicate` and `:upload` control commands to do some file
      transfer
    * Add `:export_rank` control command to uniquely identify each shell
    * Add `:show_read_buffer` control command to see what `gsh` just read
    * Print help for common SSH key problems
    * New completion from the local filesystem
    * Simplify `:list` output, and added the last printed line

Version 0.3.1
    * If the `:{en|dis}able` command would have no effect, change all other
      shells to the inverse enable value
    * Consistently add a space between the shell name and the colon to ease
      parsing the output
    * Provide exit code aggregated from all remote shells by taking
      the maximum
    * Rename `:export_rank` to `:export_vars` as it now also exports
      the hostname
    * Add `--password-file` to login using a password
    * Support `.zip` files on file transfer
    * Switch from `setuptools` to `distutils`
    * Color hostnames in the output

Version 0.4
    * Rename project to Polysh
    * Add `--user` option to specify the remote user to login as
    * New file transfer code that does not assume additional connectivity
      between the host and the remote shells but still assumes connectivity
      between the remote shells
    * Add option to disable colorized hostnames

Unreleased
    * Drop `:upload` and `:replicate` file transfer features
    * Don't forward `Ctrl-Z` to the remote shells
    * Save and restore history from `~/.polysh_hisory`
