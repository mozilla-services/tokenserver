# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to purge user records that have been replaced.

This script takes a tokenserver config file, uses it to load the assignment
backend, and then purges any obsolete user records from that backend.
Obsolete records are those that have been replaced by a newer record for
the same user.

Note that this is a purely optional administrative task, since replaced records
are handled internally by the assignment backend.  But it should help reduce
overheads, improve performance etc if run regularly.

"""

import os
import time
import logging
import optparse

import requests
import tokenlib
import hawkauthlib

import tokenserver.scripts
from tokenserver.assignment import INodeAssignment


logger = logging.getLogger("tokenserver.scripts.purge_old_records")


def purge_old_records(config_file, grace_period=-1, max_per_loop=10,
                      request_timeout=60):
    """Purge old records from the assignment backend in the given config file.

    This function iterates through each storage backend in the given config
    file and calls its purge_expired_items() method.  The result is a
    gradual pruning of expired items from each database.
    """
    logger.info("Purging old user records")
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)
    config.begin()
    try:
        backend = config.registry.getUtility(INodeAssignment)
        patterns = config.registry['endpoints_patterns']
        for service in patterns:
            logger.debug("Purging old user records for service: %s", service)
            # Process batches of <max_per_loop> items, until we run out.
            while True:
                kwds = {
                    "grace_period": grace_period,
                    "limit": max_per_loop,
                }
                rows = list(backend.get_old_user_records(service, **kwds))
                for row in rows:
                    logger.debug("Purging uid %s on %s", row.uid, row.node)
                    delete_service_data(config, service, row.uid, row.node,
                                        timeout=request_timeout)
                    backend.delete_user_record(service, row.uid)
                if len(rows) < max_per_loop:
                    break
    except Exception:
        logger.exception("Error while purging old user records")
        return False
    else:
        logger.info("Finished purging old user records")
        return True
    finally:
        config.end()


def delete_service_data(config, service, uid, node, timeout=60):
    """Send a data-deletion request to the user's service node.

    This is a little bit of hackery to cause the user's service node to
    remove any data it still has stored for the user.  We simulate a DELETE
    request from the user's own account.
    """
    secrets = config.registry.settings['tokenserver.secrets']
    pattern = config.registry['endpoints_patterns'][service]
    node_secrets = secrets.get(node)
    if not node_secrets:
        msg = "The node %r does not have any shared secret" % (node,)
        raise ValueError(msg)
    user = {"uid": uid, "node": node}
    token = tokenlib.make_token(user, secret=node_secrets[-1])
    secret = tokenlib.get_derived_secret(token, secret=node_secrets[-1])
    endpoint = pattern.format(uid=uid, service=service, node=node)
    auth = HawkAuth(token, secret)
    resp = requests.delete(endpoint, auth=auth, timeout=timeout)
    if resp.status_code >= 400 and resp.status_code != 404:
        resp.raise_for_status()


class HawkAuth(requests.auth.AuthBase):
    """Hawk-signing auth helper class."""

    def __init__(self, token, secret):
        self.token = token
        self.secret = secret

    def __call__(self, req):
        hawkauthlib.sign_request(req, self.token, self.secret)
        return req


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the purge_old_records() function.
    """
    usage = "usage: %prog [options] config_file"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("", "--purge-interval", type="int", default=3600,
                      help="Interval to sleep between purging runs")
    parser.add_option("", "--grace-period", type="int", default=86400,
                      help="Number of seconds grace to allow on replacement")
    parser.add_option("", "--max-per-loop", type="int", default=10,
                      help="Maximum number of items to fetch in one go")
    parser.add_option("", "--request-timeout", type="int", default=60,
                      help="Timeout for service deletion requests")
    parser.add_option("", "--oneshot", action="store_true",
                      help="Do a single purge run and then exit")
    parser.add_option("-v", "--verbose", action="count", dest="verbosity",
                      help="Control verbosity of log messages")

    opts, args = parser.parse_args(args)
    if len(args) != 1:
        parser.print_usage()
        return 1

    tokenserver.scripts.configure_script_logging(opts)

    config_file = os.path.abspath(args[0])

    purge_old_records(config_file,
                      grace_period=opts.grace_period,
                      max_per_loop=opts.max_per_loop,
                      request_timeout=opts.request_timeout)
    if not opts.oneshot:
        while True:
            logger.debug("Sleeping for %d seconds", opts.purge_interval)
            time.sleep(opts.purge_interval)
            purge_old_records(config_file,
                              grace_period=opts.grace_period,
                              max_per_loop=opts.max_per_loop,
                              request_timeout=opts.request_timeout)
    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
