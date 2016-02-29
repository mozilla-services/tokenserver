# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Script to process account-related events from an SQS queue.

This script polls an SQS queue for events indicating activity on an upstream
account.  The following event types are currently supported:

  * "delete":  the account was deleted; we mark their records as retired
               so they'll be cleaned up by our garbage-collection process.

  * "reset":   the account password was reset; we update our copy of their
               generation number to disconnect other devices.

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


def process_account_events(config_file, queue_name, aws_region=None,
                           queue_wait_time=20):
    """Process account events from an SQS queue.

    This function polls the specified SQS queue for account-realted events,
    processing each as it is found.  It polls indefinitely and does not return;
    to interrupt execution you'll need to e.g. SIGINT the process.
    """
    logger.info("Processing account events from %s", queue_name)
    logger.debug("Using config file %r", config_file)
    config = tokenserver.scripts.load_configurator(config_file)
    config.begin()
    try:
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
            process_account_event(config, msg.get_body())
            # This intentionally deletes the event even if it was some
            # unrecognized type.  Not point leaving a backlog.
            queue.delete_message(msg)
    except Exception:
        logger.exception("Error while processing account events")
        raise
    finally:
        config.end()


def process_account_event(config, body):
    """Parse and process a single account event."""
    backend = config.registry.getUtility(INodeAssignment)
    # Try very hard not to error out if there's junk in the queue.
    email = None
    event_type = None
    generation = None
    try:
        body = json.loads(body)
        event = json.loads(body['Message'])
        event_type = event["event"]
        email = event["uid"]
        if event_type == "reset":
            generation = event["generation"]
    except (ValueError, KeyError), e:
        logger.exception("Invalid account message: %s", e)
    else:
        if email is not None:
            if event_type == "delete":
                # Mark the user as retired.
                # Actual cleanup is done by a separate process.
                logger.info("Processing account delete for %r", email)
                backend.retire_user(email)
            elif event_type == "reset":
                # Update the generation to one less than its new value.
                # This locks out devices with younger generations
                # while ensuring we dont error out when a device with
                # the new generation shows up for the first time.
                logger.info("Processing account reset for %r", email)
                patterns = config.registry['endpoints_patterns']
                for service in patterns:
                    logger.debug("Processing account reset for service: %s",
                                 service)
                    user = backend.get_user(service, email)
                    if user is not None:
                        backend.update_user(service, user, generation - 1)
            else:
                logger.warning("Dropping unknown event type %r",
                               event_type)


def main(args=None):
    """Main entry-point for running this script.

    This function parses command-line arguments and passes them on
    to the process_account_events() function.
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

    process_account_events(config_file, queue_name,
                           opts.aws_region, opts.queue_wait_time)
    return 0


if __name__ == "__main__":
    tokenserver.scripts.run_script(main)
