# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""
SQLAlchemy-based node-assignment database.

For each available service, we maintain a list of user accounts and their
associated uid, node-assignment and metadata.  We also have a list of nodes
with their load, capacity etc
"""
import math
import traceback
from mozsvc.exceptions import BackendError

from sqlalchemy.sql import select, update, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import text as sqltext, func as sqlfunc
from sqlalchemy.exc import OperationalError, TimeoutError

from zope.interface import implements
from tokenserver.assignment import INodeAssignment
from tokenserver.util import get_timestamp


import logging
logger = logging.getLogger('tokenserver.assignment.sqlnode')


# The maximum possible generation number.
# Used as a tombstone to mark users that have been "retired" from the db.
MAX_GENERATION = 9223372036854775807


NODE_FIELDS = ("capacity", "available", "current_load", "downed", "backoff")


_Base = declarative_base()


_GET_USER_RECORDS = sqltext("""\
select
    uid, nodes.node, generation, client_state, created_at, replaced_at
from
    users left outer join nodes on users.nodeid = nodes.id
where
    email = :email and users.service = :service
order by
    created_at desc, uid desc
limit
    20
""")


_CREATE_USER_RECORD = sqltext("""\
insert into
    users
    (service, email, nodeid, generation, client_state, created_at, replaced_at)
values
    (:service, :email, :nodeid, :generation, :client_state, :timestamp, NULL)
""")


_UPDATE_GENERATION_NUMBER = sqltext("""\
update
    users
set
    generation = :generation
where
    service = :service and email = :email and
    generation < :generation and replaced_at is null
""")


_REPLACE_USER_RECORDS = sqltext("""\
update
    users
set
    replaced_at = :timestamp
where
    service = :service and email = :email
    and replaced_at is null and created_at < :timestamp
""")


# Mark all records for the user as replaced,
# and set a large generation number to block future logins.
_RETIRE_USER_RECORDS = sqltext("""\
update
    users
set
    replaced_at = :timestamp,
    generation = :generation
where
    email = :email
    and replaced_at is null
""")


_GET_OLD_USER_RECORDS_FOR_SERVICE = sqltext("""\
select
    uid, email, client_state, nodes.node, created_at, replaced_at
from
    users left outer join nodes on users.nodeid = nodes.id
where
    users.service = :service
and
    replaced_at is not null and replaced_at < :timestamp
order by
    replaced_at desc, uid desc
limit
    :limit
""")


_GET_ALL_USER_RECORDS_FOR_SERVICE = sqltext("""\
select
    uid, nodes.node, created_at, replaced_at
from
    users left outer join nodes on users.nodeid = nodes.id
where
    email = :email and users.service = :service
order by
    created_at asc, uid desc
""")


_REPLACE_USER_RECORD = sqltext("""\
update
    users
set
    replaced_at = :timestamp
where
    service = :service
and
    uid = :uid
""")


_DELETE_USER_RECORD = sqltext("""\
delete from
    users
where
    service = :service
and
    uid = :uid
""")


_FREE_SLOT_ON_NODE = sqltext("""\
update
    nodes
set
    available = available + 1, current_load = current_load - 1
where
    id = (SELECT nodeid FROM users WHERE service=:service AND uid=:uid)
""")


_COUNT_USER_RECORDS = sqltext("""\
select
    count(email)
from
    users
where
    replaced_at is null
    and created_at <= :timestamp
""")


class SQLNodeAssignment(object):

    implements(INodeAssignment)

    def __init__(self, sqluri, create_tables=False, pool_size=100,
                 pool_recycle=60, pool_timeout=30, max_overflow=10,
                 pool_reset_on_return='rollback', capacity_release_rate=0.1,
                 **kw):
        self._cached_service_ids = {}
        self.sqluri = sqluri
        if pool_reset_on_return.lower() in ('', 'none'):
            pool_reset_on_return = None

        # Use production-ready pool settings for the MySQL backend.
        # We also need to work around mysql using "LEAST(a,b)" and
        # sqlite using "MIN(a,b)" in expressions.
        if sqluri.startswith('mysql') or sqluri.startswith('pymysql'):
            self._engine = create_engine(
                sqluri,
                pool_size=pool_size,
                pool_recycle=pool_recycle,
                pool_timeout=pool_timeout,
                pool_reset_on_return=pool_reset_on_return,
                max_overflow=max_overflow,
                logging_name='tokenserver.assignment.sqlnode'
            )
            self._sqlfunc_min = sqlfunc.least
        else:
            self._engine = create_engine(sqluri, poolclass=NullPool)
            self._sqlfunc_min = sqlfunc.min

        self._engine.echo = kw.get('echo', False)
        self.capacity_release_rate = capacity_release_rate

        self._is_sqlite = (self._engine.driver == 'pysqlite')
        if self._is_sqlite:
            from tokenserver.assignment.sqlnode.sqliteschemas import get_cls
        else:
            from tokenserver.assignment.sqlnode.schemas import get_cls

        self.services = get_cls('services', _Base)
        self.nodes = get_cls('nodes', _Base)
        self.users = get_cls('users', _Base)

        for table in (self.services, self.nodes, self.users):
            table.metadata.bind = self._engine
            if create_tables:
                table.create(checkfirst=True)

    def _get_engine(self, service=None):
        return self._engine

    def _safe_execute(self, *args, **kwds):
        """Execute an sqlalchemy query, raise BackendError on failure."""
        if hasattr(args[0], 'bind'):
            engine = args[0].bind
        else:
            engine = None

        if engine is None:
            engine = kwds.pop('engine', None)
            if engine is None:
                engine = self._get_engine(kwds.get('service'))

        if 'service' in kwds:
            kwds['service'] = self._get_service_id(kwds['service'])

        try:
            return engine.execute(*args, **kwds)
        except (OperationalError, TimeoutError), exc:
            err = traceback.format_exc()
            logger.error(err)
            raise BackendError(str(exc))

    def get_user(self, service, email):
        params = {'service': service, 'email': email}
        res = self._safe_execute(_GET_USER_RECORDS, **params)
        try:
            # The query fetches rows ordered by created_at, but we want
            # to ensure that they're ordered by (generation, created_at).
            # This is almost always true, except for strange race conditions
            # during row creation.  Sorting them is an easy way to enforce
            # this without bloating the db index.
            rows = res.fetchall()
            rows.sort(key=lambda r: (r.generation, r.created_at), reverse=True)
            if not rows:
                return None
            # The first row is the most up-to-date user record.
            # The rest give previously-seen client-state values.
            cur_row = rows[0]
            old_rows = rows[1:]
            user = {
                'email': email,
                'uid': cur_row.uid,
                'node': cur_row.node,
                'generation': cur_row.generation,
                'client_state': cur_row.client_state,
                'old_client_states': {},
                'first_seen_at': cur_row.created_at
            }
            # If the current row is marked as replaced or is missing a node,
            # and they haven't been retired, then assign them a new node.
            if cur_row.replaced_at is not None or cur_row.node is None:
                if cur_row.generation < MAX_GENERATION:
                    user = self.allocate_user(service, email,
                                              cur_row.generation,
                                              cur_row.client_state)
            for old_row in old_rows:
                # Collect any previously-seen client-state values.
                if old_row.client_state != user['client_state']:
                    user['old_client_states'][old_row.client_state] = True
                # Make sure each old row is marked as replaced.
                # They might not be, due to races in row creation.
                if old_row.replaced_at is None:
                    timestamp = cur_row.created_at
                    self.replace_user_record(service, old_row.uid, timestamp)
                # Track backwards to the oldest timestamp at which we saw them.
                user['first_seen_at'] = old_row.created_at
            return user
        finally:
            res.close()

    def allocate_user(self, service, email, generation=0, client_state='',
                      node=None, timestamp=None):
        if timestamp is None:
            timestamp = get_timestamp()
        if node is None:
            nodeid, node = self.get_best_node(service)
        else:
            nodeid = self.get_node_id(service, node)
        params = {
            'service': service, 'email': email, 'nodeid': nodeid,
            'generation': generation, 'client_state': client_state,
            'timestamp': timestamp
        }
        res = self._safe_execute(_CREATE_USER_RECORD, **params)
        res.close()
        return {
            'email': email,
            'uid': res.lastrowid,
            'node': node,
            'generation': generation,
            'client_state': client_state,
            'old_client_states': {},
            'first_seen_at': timestamp
        }

    def update_user(self, service, user, generation=None, client_state=None,
                    node=None):
        if client_state is None and node is None:
            # We're just updating the generation, re-use the existing record.
            if generation is not None:
                params = {
                    'service': service,
                    'email': user['email'],
                    'generation': generation
                }
                res = self._safe_execute(_UPDATE_GENERATION_NUMBER, **params)
                res.close()
                user['generation'] = max(generation, user['generation'])
        else:
            # Reject previously-seen client-state strings.
            if client_state is None:
                client_state = user['client_state']
            else:
                if client_state == user['client_state']:
                    raise BackendError('previously seen client-state string')
                if client_state in user['old_client_states']:
                    raise BackendError('previously seen client-state string')
            # Need to create a new record for new user state.
            # If the node is not explicitly changing, try to keep them on the
            # same node, but if e.g. it no longer exists them allocate them to
            # a new one.
            if node is not None:
                nodeid = self.get_node_id(service, node)
                user['node'] = node
            else:
                try:
                    nodeid = self.get_node_id(service, user['node'])
                except ValueError:
                    nodeid, node = self.get_best_node(service)
                    user['node'] = node
            if generation is not None:
                generation = max(user['generation'], generation)
            else:
                generation = user['generation']
            now = get_timestamp()
            params = {
                'service': service, 'email': user['email'],
                'nodeid': nodeid, 'generation': generation,
                'client_state': client_state, 'timestamp': now,
            }
            res = self._safe_execute(_CREATE_USER_RECORD, **params)
            res.close()
            user['uid'] = res.lastrowid
            user['generation'] = generation
            user['old_client_states'][user['client_state']] = True
            user['client_state'] = client_state
            # mark old records as having been replaced.
            # if we crash here, they are unmarked and we may fail to
            # garbage collect them for a while, but the active state
            # will be undamaged.
            self.replace_user_records(service, user['email'], now)

    def retire_user(self, email, engine=None):
        now = get_timestamp()
        params = {
            'email': email, 'timestamp': now, 'generation': MAX_GENERATION
        }
        # Pass through explicit engine to help with sharded implementation,
        # since we can't shard by service name here.
        res = self._safe_execute(_RETIRE_USER_RECORDS, engine=engine, **params)
        res.close()

    def count_users(self, timestamp=None):
        if timestamp is None:
            timestamp = get_timestamp()
        res = self._safe_execute(_COUNT_USER_RECORDS, timestamp=timestamp)
        row = res.fetchone()
        res.close()
        return row[0]

    #
    # Methods for low-level user record management.
    #

    def get_user_records(self, service, email):
        """Get all the user's records for a service, including the old ones."""
        params = {'service': service, 'email': email}
        res = self._safe_execute(_GET_ALL_USER_RECORDS_FOR_SERVICE, **params)
        try:
            for row in res:
                yield row
        finally:
            res.close()

    def get_old_user_records(self, service, grace_period=-1, limit=100):
        """Get user records that were replaced outside the grace period."""
        if grace_period < 0:
            grace_period = 60 * 60 * 24 * 7  # one week, in seconds
        grace_period = int(grace_period * 1000)  # convert seconds -> millis
        params = {
            "service": service,
            "timestamp": get_timestamp() - grace_period,
            "limit": limit,
        }
        res = self._safe_execute(_GET_OLD_USER_RECORDS_FOR_SERVICE, **params)
        try:
            for row in res:
                yield row
        finally:
            res.close()

    def replace_user_records(self, service, email, timestamp=None):
        """Mark all existing service records for a user as replaced."""
        if timestamp is None:
            timestamp = get_timestamp()
        params = {
            'service': service, 'email': email, 'timestamp': timestamp
        }
        res = self._safe_execute(_REPLACE_USER_RECORDS, **params)
        res.close()

    def replace_user_record(self, service, uid, timestamp=None):
        """Mark an existing service record as replaced."""
        if timestamp is None:
            timestamp = get_timestamp()
        params = {
            'service': service, 'uid': uid, 'timestamp': timestamp
        }
        res = self._safe_execute(_REPLACE_USER_RECORD, **params)
        res.close()

    def delete_user_record(self, service, uid):
        """Delete the user record with the given uid."""
        params = {'service': service, 'uid': uid}
        res = self._safe_execute(_FREE_SLOT_ON_NODE, **params)
        res.close()
        res = self._safe_execute(_DELETE_USER_RECORD, **params)
        res.close()

    #
    # Nodes management
    #

    def _get_service_id(self, service):
        try:
            return self._cached_service_ids[service]
        except KeyError:
            services = self._get_services_table(service)
            query = select([services.c.id])
            query = query.where(services.c.service == service)
            res = self._safe_execute(query)
            row = res.fetchone()
            res.close()
            if row is None:
                raise BackendError('unknown service: ' + service)
            self._cached_service_ids[service] = row.id
            return row.id

    def get_patterns(self):
        """Returns all the service URL patterns."""
        query = select([self.services])
        res = self._safe_execute(query)
        patterns = list(res.fetchall())
        for row in patterns:
            self._cached_service_ids[row.service] = row.id
        res.close()
        return dict([(row.service, row.pattern) for row in patterns])

    def add_service(self, service, pattern, **kwds):
        """Add definition for a new service."""
        res = self._safe_execute(sqltext("""
          insert into services (service, pattern)
          values (:servicename, :pattern)
        """), servicename=service, pattern=pattern, **kwds)
        res.close()
        return res.lastrowid

    def add_node(self, service, node, capacity, **kwds):
        """Add definition for a new node."""
        available = kwds.get('available')
        # We release only a fraction of the node's capacity to start.
        if available is None:
            available = math.ceil(capacity * self.capacity_release_rate)
        res = self._safe_execute(sqltext(
            """
            insert into nodes (service, node, available, capacity,
                               current_load, downed, backoff)
            values (:service, :node, :available, :capacity,
                    :current_load, :downed, :backoff)
            """),
            service=service, node=node, capacity=capacity, available=available,
            current_load=kwds.get('current_load', 0),
            downed=kwds.get('downed', 0),
            backoff=kwds.get('backoff', 0),
        )
        res.close()

    def update_node(self, service, node, **kwds):
        """Updates node fields in the db."""

        nodes = self._get_nodes_table(service)
        service = self._get_service_id(service)

        where = [nodes.c.service == service, nodes.c.node == node]
        where = and_(*where)
        values = {}
        for field in NODE_FIELDS:
            try:
                values[field] = kwds.pop(field)
            except KeyError:
                pass
        if kwds:
            raise ValueError("unknown fields: " + str(kwds.keys()))
        query = update(nodes, where, values)
        con = self._safe_execute(query, close=True)
        con.close()

    def get_node_id(self, service, node):
        """Get numeric id for a node."""
        res = self._safe_execute(sqltext(
            """
            select id from nodes
            where service=:service and node=:node
            """),
            service=service, node=node
        )
        row = res.fetchone()
        res.close()
        if row is None:
            raise ValueError("unknown node: " + node)
        return row[0]

    def remove_node(self, service, node, timestamp=None):
        """Remove definition for a node."""
        nodeid = self.get_node_id(service, node)
        res = self._safe_execute(sqltext(
            """
            delete from nodes where id=:nodeid
            """),
            service=service, nodeid=nodeid
        )
        res.close()
        self.unassign_node(service, node, timestamp, nodeid=nodeid)

    def unassign_node(self, service, node, timestamp=None, nodeid=None):
        """Clear any assignments to a node."""
        if timestamp is None:
            timestamp = get_timestamp()
        if nodeid is None:
            nodeid = self.get_node_id(service, node)
        res = self._safe_execute(sqltext(
            """
            update users
            set replaced_at=:timestamp
            where nodeid=:nodeid
            """),
            nodeid=nodeid, timestamp=timestamp
        )
        res.close()

    def get_best_node(self, service):
        """Returns the 'least loaded' node currently available, increments the
        active count on that node, and decrements the slots currently available
        """
        nodes = self._get_nodes_table(service)
        service = self._get_service_id(service)

        # Pick the least-loaded node that has available slots.
        where = [nodes.c.service == service,
                 nodes.c.available > 0,
                 nodes.c.capacity > nodes.c.current_load,
                 nodes.c.downed == 0,
                 nodes.c.backoff == 0]

        query = select([nodes]).where(and_(*where))

        if self._is_sqlite:
            # sqlite doesn't have the 'log' funtion, and requires
            # coercion to a float for the sorting to work.
            query = query.order_by(nodes.c.current_load * 1.0 /
                                   nodes.c.capacity)
        else:
            # using log() increases floating-point precision on mysql
            # and thus makes the sorting more accurate.
            query = query.order_by(sqlfunc.log(nodes.c.current_load) /
                                   sqlfunc.log(nodes.c.capacity))
        query = query.limit(1)

        # We may have to re-try the query if we need to release more capacity.
        # This loop allows a maximum of five retries before bailing out.
        for _ in xrange(5):
            res = self._safe_execute(query)
            row = res.fetchone()
            res.close()
            if row is None:
                # Try to release additional capacity from any nodes
                # that are not fully occupied.
                where = and_(nodes.c.service == service,
                             nodes.c.available <= 0,
                             nodes.c.capacity > nodes.c.current_load,
                             nodes.c.downed == 0)
                fields = {
                    'available': self._sqlfunc_min(
                        nodes.c.capacity * self.capacity_release_rate,
                        nodes.c.capacity - nodes.c.current_load
                    ),
                }
                res = self._safe_execute(update(nodes, where, fields))
                res.close()
                if res.rowcount == 0:
                    break

        # Did we succeed in finding a node?
        if row is None:
            raise BackendError('unable to get a node')

        nodeid = row.id
        node = str(row.node)

        # Update the node to reflect the new assignment.
        # This is a little racy with concurrent assignments, but no big deal.
        where = [nodes.c.service == service, nodes.c.node == node]
        where = and_(*where)
        fields = {'available': nodes.c.available - 1,
                  'current_load': nodes.c.current_load + 1}
        query = update(nodes, where, fields)
        con = self._safe_execute(query, close=True)
        con.close()

        return nodeid, node

    def _get_services_table(self, service):
        return self.services

    def _get_nodes_table(self, service):
        return self.nodes

    def _get_users_table(self, service):
        return self.users
