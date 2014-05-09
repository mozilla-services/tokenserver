# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to remove a node from the system.

This script takes a tokenserver config file, uses it to load the assignment
backend, and then clears any assignments to the named node.

"""

import os
import logging
import optparse

import tokenserver.scripts
from tokenserver.assignment import INodeAssignment


logger = logging.getLogger("tokenserver.scripts.unassign_node")


def unassign_node(config_file, node):
    """Clear any assignments to the named node."""
    logger.info("Unassignment node %s", node)
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)
    config.begin()
    try:
        backend = config.registry.getUtility(INodeAssignment)
        patterns = config.registry['endpoints_patterns']
        found = False
        for service in patterns:
            logger.debug("Unassigning node for service: %s", service)
            try:
                backend.unassign_node(service, node)
            except ValueError:
                logger.debug("  not found")
            else:
                found = True
                logger.debug("  unassigned")
    except Exception:
        logger.exception("Error while unassigning node")
        return False
    else:
        if not found:
            logger.info("Node %s was not found", node)
        else:
            logger.info("Finished unassigning node %s", node)
        return True
    finally:
        config.end()


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the unassign_node() function.
    """
    usage = "usage: %prog [options] config_file node_name"
    descr = "Clear all assignments to node in the tokenserver database"
    parser = optparse.OptionParser(usage=usage, description=descr)
    parser.add_option("-v", "--verbose", action="count", dest="verbosity",
                      help="Control verbosity of log messages")

    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_usage()
        return 1

    tokenserver.scripts.configure_script_logging(opts)

    config_file = os.path.abspath(args[0])
    node_name = args[1]

    unassign_node(config_file, node_name)
    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
