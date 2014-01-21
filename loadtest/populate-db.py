#! /usr/bin/env python
# script to populate the database with records
import time
import random
from wimms.sql import SQLMetadata, _CREATE_USER_RECORD


def populate_db(sqluri, service, nodes, user_range, host="loadtest.local"):
    """Create a bunch of users for the given service.

    The resulting users will have an adress in the form of <uid>@<host> where
    uid is an int from 0 to :param user_range:.

    This function is useful to populate the database during the loadtest. It
    allows to test a specific behaviour: making sure that we are not reading
    the values from memory when retrieving the node information.

    :param sqluri: the sqluri string used to connect to the database
    :param service: the service to assign the users to.
    :param nodes: the list of availables nodes for this service
    :param user_range: the number of users to create
    :param host: the hostname to use when generating users
    """
    params = {
        'service': service,
        'generation': 0,
        'client_state': '',
        'timestamp': int(time.time() * 1000),
    }
    # for each user in the range, assign him to a node
    md = SQLMetadata(sqluri, create_tables=True)
    for idx in range(0, user_range):
        email = "%s@%s" % (idx, host)
        node = random.choice(nodes)
        md._safe_execute(_CREATE_USER_RECORD, email=email, node=node, **params)


def main():
    """Read the arguments from the command line and pass them to the
    populate_db function.

    Example use:

        python populate-db.py sqlite:////tmp/tokenserver aitc\
        node1,node2,node3,node4,node5,node6 100
    """
    import sys
    if len(sys.argv) < 5:
        raise ValueError('You need to specify (in this order) sqluri, '
                         'service, nodes (comma separated) and user_range')
    # transform the values from the cli to python objects
    sys.argv[3] = sys.argv[3].split(',')  # comma separated => list
    sys.argv[4] = int(sys.argv[4])

    populate_db(*sys.argv[1:])
    print("created {nb_users} users".format(nb_users=sys.argv[4]))


if __name__ == '__main__':
    main()
