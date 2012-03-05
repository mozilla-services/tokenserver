""" SQL Mappers
"""
from zope.interface import implements
from tokenserver.assignment import INodeAssignment

from wimms.sql import SQLMetadata
from wimms.shardedsql import ShardedSQLMetadata


class SQLNodeAssignment(SQLMetadata):
    """Just a placeholder to mark with a zope interface.

    Silly, isn't it ?
    """
    implements(INodeAssignment)


class ShardedSQLNodeAssignment(ShardedSQLMetadata):
    implements(INodeAssignment)
