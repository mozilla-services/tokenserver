# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Table schema for MySQL and sqlite.

We have the following tables:

 services:  lists the available services and their endpoint-url pattern.
 nodes:  lists the nodes available for each service.
 users:  lists the user records for each service, along with their
         metadata and current node assignment.

"""

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, Integer, String, BigInteger, Index


bases = {}


def _add(name, base):
    bases[name] = base


def get_cls(name, base_cls):
    if name in base_cls.metadata.tables:
        return base_cls.metadata.tables[name]

    args = {'__tablename__': name}
    base = bases[name]
    return type(name, (base, base_cls), args).__table__


class _UsersBase(object):
    """This table associates email addresses with services via integer uids.

    A user is uniquely identified by their email.  For each service they have
    a uid, an allocated node, and last-seen generation and client-state values.
    Rows are timestamped for easy cleanup of old records.
    """
    uid = Column(BigInteger(), primary_key=True, autoincrement=True,
                 nullable=False)
    service = Column(Integer(), nullable=False)
    email = Column(String(255), nullable=False)
    node = Column(String(64), nullable=False)
    generation = Column(BigInteger(), nullable=False)
    client_state = Column(String(32), nullable=False)
    created_at = Column(BigInteger(), nullable=False)
    replaced_at = Column(BigInteger(), nullable=True)

    @declared_attr
    def __table_args__(cls):
        return (
            # Index used to slurp in all records for a (service, email)
            # pair, sorted by creation time.
            Index('lookup_idx', 'email', 'service', 'created_at'),
            # Index used for purging user_records that have been replaced.
            Index('replaced_at_idx', 'service', 'replaced_at'),
            # Index used for looking up all assignments on a node.
            Index('node_idx', 'service', 'node'),
            {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}
        )

_add('users', _UsersBase)


class _ServicesBase(object):
    """This table lists all the available services and their endpoint patterns.

    Service names are expected to be "{app_name}-{app_version}" for example
    "sync-1.5".  Endpoint patterns can use python formatting options on the
    keys {uid}, {node} and {service}.

    Having a table for these means that we can internally refer to each service
    by an integer key, which helps when indexing by service.
    """
    id = Column(Integer(), primary_key=True, autoincrement=True,
                nullable=False)
    service = Column(String(30), unique=True)
    pattern = Column(String(128))

_add('services', _ServicesBase)


class _NodesBase(object):
    """This table keeps tracks of all nodes available per service

    Each node has a root URL as well as metadata about its current availability
    and capacity.
    """
    id = Column(BigInteger(), primary_key=True, autoincrement=True,
                nullable=False)
    service = Column(Integer(), nullable=False)
    node = Column(String(64), nullable=False)
    available = Column(Integer, default=0, nullable=False)
    current_load = Column(Integer, default=0, nullable=False)
    capacity = Column(Integer, default=0, nullable=False)
    downed = Column(Integer, default=0, nullable=False)
    backoff = Column(Integer, default=0, nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (
            Index('unique_idx', 'service', 'node', unique=True),
            {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8'}
        )

_add('nodes', _NodesBase)
