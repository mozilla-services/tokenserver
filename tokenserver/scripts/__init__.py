# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Admin/managment scripts for TokenServer.

"""

import sys
import logging

import tokenserver


def run_script(main):
    """Simple wrapper for running scripts in __main__ section."""
    try:
        exitcode = main()
    except KeyboardInterrupt:
        exitcode = 1
    sys.exit(exitcode)


def load_configurator(config_file):
    """Load a TokenServer configurator object from the given config file.

    This is a lightweight wrapper around tokenserver.get_configurator(),
    which adds some configuration tweaks for running in a script instead of
    as an long-running application.
    """
    config = tokenserver.get_configurator({"__file__": config_file})
    config.include(tokenserver)
    config.commit()
    return config


def configure_script_logging(opts=None):
    """Configure stdlib logging to produce output from the script.

    This basically configures logging to send messages to stderr, with
    formatting that's more for human readability than machine parsing.
    It also takes care of the --verbosity command-line option.
    """
    if not opts or not opts.verbosity:
        loglevel = logging.WARNING
    elif opts.verbosity == 1:
        loglevel = logging.INFO
    else:
        loglevel = logging.DEBUG

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(loglevel)
    logger = logging.getLogger("")
    logger.addHandler(handler)
    logger.setLevel(loglevel)
