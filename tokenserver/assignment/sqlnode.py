""" SQL Mappers
"""
from zope.interface import implements
from tokenserver.assignment import INodeAssignment
from tokenlib.metadata.sql import SQLMetadata


class SQLNodeAssignment(SQLMetadata):
    """Just a placeholder to mark with a zope interface.

    Silly, isn't it ?
    """
    implements(INodeAssignment)
