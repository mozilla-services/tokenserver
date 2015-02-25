# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to emit total-user-count metrics for exec dashboard.

This script takes a tokenserver config file, uses it to load the assignment
backend, and then outputs the reported user count.

"""

import os
import sys
import time
import json
import socket
import optparse
from datetime import datetime, timedelta, tzinfo

from tokenserver.assignment import INodeAssignment
import tokenserver.scripts

import logging
logger = logging.getLogger("tokenserver.scripts.count_users")

ZERO = timedelta(0)


class UTC(tzinfo):

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()


def count_users(config_file, outfile, timestamp=None):
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)
    config.begin()
    try:
        if timestamp is None:
            ts = time.gmtime()
            midnight = (ts[0], ts[1], ts[2], 0, 0, 0, ts[6], ts[7], ts[8])
            timestamp = int(time.mktime(midnight)) * 1000
        backend = config.registry.getUtility(INodeAssignment)
        logger.debug("Counting users created before %i", timestamp)
        count = backend.count_users(timestamp)
        logger.debug("Found %d users", count)
        # Output has heka-filter-compatible JSON object.
        ts_sec = timestamp / 1000
        output = {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "op": "sync_count_users",
            "total_users": count,
            "time": datetime.fromtimestamp(ts_sec, utc).isoformat(),
            "v": 0
        }
        json.dump(output, outfile)
        outfile.write("\n")
    finally:
        config.end()


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the add_node() function.
    """
    usage = "usage: %prog [options] config_file"
    descr = "Count total users in the tokenserver database"
    parser = optparse.OptionParser(usage=usage, description=descr)
    parser.add_option("-t", "--timestamp", type="int",
                      help="Max creation timestamp; default previous midnight")
    parser.add_option("-o", "--output",
                      help="Output file; default stderr")
    parser.add_option("-v", "--verbose", action="count", dest="verbosity",
                      help="Control verbosity of log messages")

    opts, args = parser.parse_args(args)
    if len(args) != 1:
        parser.print_usage()
        return 1

    tokenserver.scripts.configure_script_logging(opts)

    config_file = os.path.abspath(args[0])
    if opts.output in (None, "-"):
        count_users(config_file, sys.stdout, opts.timestamp)
    else:
        with open(opts.output, "a") as outfile:
            count_users(config_file, outfile, opts.timestamp)

    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
