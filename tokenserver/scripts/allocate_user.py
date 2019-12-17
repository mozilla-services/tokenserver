# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to allocate a specific user to a node.

This script takes a tokenserver config file, uses it to load the assignment
backend, and then allocates the specified user to a node.  A particular node
may be specified, or the best available node used by default.

The allocated node is printed to stdout.

"""

import os
import logging
import optparse

import tokenserver.scripts
from tokenserver.assignment import INodeAssignment


logger = logging.getLogger("tokenserver.scripts.allocate_user")


def allocate_user(config, service, email, node=None):
    logger.info("Allocating node for user %s", email)
    config.begin()
    try:
        backend = config.registry.getUtility(INodeAssignment)
        user = backend.get_user(service, email)
        if user is None:
            user = backend.allocate_user(service, email, node=node)
        else:
            backend.update_user(service, user, node=node)
        print user["node"]
    except Exception:
        logger.exception("Error while updating node")
        return False
    else:
        logger.info("Finished updating node %s", node)
        return True
    finally:
        config.end()


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the allocate_user() function.
    """
    usage = "usage: %prog [options] config_file service email [node_name]"
    descr = "Allocate a user to a node.  You may specify a particular node, "\
            "or omit to use the best available node."
    parser = optparse.OptionParser(usage=usage, description=descr)
    parser.add_option("-v", "--verbose", action="count", dest="verbosity",
                      help="Control verbosity of log messages")

    opts, args = parser.parse_args(args)
    if not 3 <= len(args) <= 4:
        parser.print_usage()
        return 1

    tokenserver.scripts.configure_script_logging(opts)

    config_file = os.path.abspath(args[0])
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)

    service = args[1]
    email = args[2]
    if len(args) == 3:
        node_name = None
    else:
        node_name = args[3]

    allocate_user(config, service, email, node_name)
    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
