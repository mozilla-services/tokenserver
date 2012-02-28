""" SQL Mappers
"""
import traceback
from zope.interface import implements
from mozsvc.exceptions import BackendError

from sqlalchemy.ext.declarative import declarative_base, Column
from sqlalchemy import Integer, String, create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import text as sqltext
from sqlalchemy.exc import OperationalError, TimeoutError

from tokenserver.assignment import INodeAssignment
from tokenserver import logger


_Base = declarative_base()


class Nodes(_Base):
    """This table lists all the users associated to a service.

    A user is represented by an email, a uid and a node.
    """
    __tablename__ = 'nodes'
    uid = Column(Integer(11), primary_key=True)
    email = Column(String(128), index=True, unique=True)

    node = Column(String(128), nullable=False)
    service = Column(String(6), nullable=False)


nodes = Nodes.__table__


_GET = sqltext("""\
select
    uid, node
from
    nodes
where
    email = :email
and
    service = :service
""")


_INSERT = sqltext("""\
insert into nodes
    (service, email, node)
values
    (:service, :email, :node)
""")




class SQLNodeAssignment(object):
    implements(INodeAssignment)

    def __init__(self, sqluri, create_tables=False, **kw):
        self.sqluri = sqluri
        self._engine = create_engine(sqluri, poolclass=NullPool)
        nodes.metadata.bind = self._engine
        if create_tables:
            nodes.create(checkfirst=True)

    def get_node(self, email, service):
        res = self._safe_execute(_GET, email=email, service=service)
        res = res.fetchone()
        if res is None:
            return None, None
        return res.uid, res.node

    def create_node(self, email, service):
        if self.get_node(email, service) != (None, None):
            raise BackendError("Node already assigned")

        # getting a node
        node = 'phx12'   # assign it

        # saving the node
        res = self._safe_execute(_INSERT, email=email, service=service,
                                 node=node)

        # returning the node and last inserted uid
        return res.lastrowid, node

    def _safe_execute(self, *args, **kwds):
        """Execute an sqlalchemy query, raise BackendError on failure."""
        try:
            return self._engine.execute(*args, **kwds)
        except (OperationalError, TimeoutError), exc:
            err = traceback.format_exc()
            logger.error(err)
            raise BackendError(str(exc))
