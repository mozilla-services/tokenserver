# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to remove a node from the system.

This script takes a tokenserver config file, uses it to load the assignment
backend, and then nukes any references to the named node - it is removed from
the "nodes" table and any users currently assigned to that node have their
assignments cleared.

"""

import os
import logging
import optparse

import tokenserver.scripts
from tokenserver.assignment import INodeAssignment


logger = logging.getLogger("tokenserver.scripts.remove_node")


def remove_node(config_file, node):
    """Remove the named node from the system."""
    logger.info("Removing node %s", node)
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)
    config.begin()
    try:
        backend = config.registry.getUtility(INodeAssignment)
        patterns = config.registry['endpoints_patterns']
        found = False
        for service in patterns:
            logger.debug("Removing node for service: %s", service)
            try:
                backend.remove_node(service, node)
            except ValueError:
                logger.debug("  not found")
            else:
                found = True
                logger.debug("  removed")
    except Exception:
        logger.exception("Error while removing node")
        return False
    else:
        if not found:
            logger.info("Node %s was not found", node)
        else:
            logger.info("Finished removing node %s", node)
        return True
    finally:
        config.end()


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the remove_node() function.
    """
    usage = "usage: %prog [options] config_file node_name"
    descr = "Remove a node from the tokenserver database"
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

    remove_node(config_file, node_name)
    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
