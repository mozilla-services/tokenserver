# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to process account-deletion events from an SQS queue.

This script polls an SQS queue for events indicating that an upstream account
has been deleted.  Any user records for such an account are marked as "retired"
so that they'll be cleaned up by our standard garbage-collection process.

Note that this is a purely optional administrative task, highly specific to
Mozilla's internal Firefox-Accounts-supported deployment.

"""

import os
import json
import logging
import optparse

import boto
import boto.ec2
import boto.sqs
import boto.sqs.message
import boto.utils

import tokenserver.scripts
from tokenserver.assignment import INodeAssignment


logger = logging.getLogger("tokenserver.scripts.process_account_deletions")


def process_account_deletions(config_file, queue_name, aws_region=None,
                              queue_wait_time=20):
    """Process account-deletion events from an SQS queue.

    This function polls the specified SQS queue for account-deletion events,
    processing each as it is found.  It polls indefinitely and does not return;
    to interrupt execution you'll need to e.g. SIGINT the process.
    """
    logger.info("Processing account deletion events from %s", queue_name)
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)
    config.begin()
    try:
        backend = config.registry.getUtility(INodeAssignment)
        # Connect to the SQS queue.
        # If no region is given, infer it from the instance metadata.
        if aws_region is None:
            logger.debug("Finding default region from instance metadata")
            aws_info = boto.utils.get_instance_metadata()
            aws_region = aws_info["placement"]["availability-zone"][:-1]
        logger.debug("Connecting to queue %r in %r", queue_name, aws_region)
        conn = boto.sqs.connect_to_region(aws_region)
        queue = conn.get_queue(queue_name)
        # We must force boto not to b64-decode the message contents, ugh.
        queue.set_message_class(boto.sqs.message.RawMessage)
        # Poll for messages indefinitely.
        while True:
            msg = queue.read(wait_time_seconds=queue_wait_time)
            if msg is None:
                continue
            # The queue should contain *only* account-deletion messages.
            # But we try very hard not to error out if there's other junk.
            try:
                body = json.loads(msg.get_body())
                event = json.loads(body['Message'])
                if event["event"] != "delete":
                    msg = "non-delete event in the queue: %s" % (event,)
                    raise ValueError(msg)
                email = event["uid"]
            except (ValueError, KeyError), e:
                logger.exception("Invalid account-delete message: %s", e)
            else:
                # Mark the user as retired.
                # Actual cleanup is done by a separate process.
                logger.info("Processing account deletion for %r", email)
                backend.retire_user(email)
            queue.delete_message(msg)
            msg = queue.read(wait_time_seconds=queue_wait_time)
    except Exception:
        logger.exception("Error while processing account deletion events")
        raise
    finally:
        config.end()


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the process_account_deletions() function.
    """
    usage = "usage: %prog [options] config_file queue_name"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("", "--aws-region",
                      help="aws region in which the queue can be found")
    parser.add_option("", "--queue-wait-time", type="int", default=20,
                      help="Number of seconds to wait for jobs on the queue")
    parser.add_option("-v", "--verbose", action="count", dest="verbosity",
                      help="Control verbosity of log messages")

    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_usage()
        return 1

    tokenserver.scripts.configure_script_logging(opts)

    config_file = os.path.abspath(args[0])
    queue_name = args[1]

    process_account_deletions(config_file, queue_name,
                              opts.aws_region, opts.queue_wait_time)
    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
