""" SQL Mappers
"""
import traceback
from zope.interface import implements
from mozsvc.exceptions import BackendError

from sqlalchemy.sql import select, update, and_
from sqlalchemy.ext.declarative import declarative_base, Column
from sqlalchemy import Integer, String, create_engine, BigInteger
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import text as sqltext
from sqlalchemy.exc import OperationalError, TimeoutError

from tokenserver.assignment import INodeAssignment
from tokenserver import logger


_Base = declarative_base()
tables = []


def get_user_nodes_table(driver):
    if 'user_nodes' in _Base.metadata.tables:
        return _Base.metadata.tables['user_nodes']

    if driver != 'pysqlite':
        class UserNodes(_Base):
            """This table lists all the users associated to a service.

            A user is represented by an email, a uid and its allocated node.
            """
            __tablename__ = 'user_nodes'
            email = Column(String(128), primary_key=True, index=True)
            node = Column(String(64), primary_key=True, nullable=False)
            service = Column(String(30), primary_key=True, nullable=False)
            uid = Column(BigInteger(), index=True, autoincrement=True, unique=True,
                        nullable=False)

        return UserNodes.__table__
    else:

        class UserNodes(_Base):
            """Sqlite version"""
            __tablename__ = 'user_nodes'
            email = Column(String(128))
            node = Column(String(64), nullable=False)
            service = Column(String(30), nullable=False)
            uid = Column(Integer(11), primary_key=True, autoincrement=True)

        return UserNodes.__table__


class Nodes(_Base):
    """A Table that keep tracks of all nodes per service
    """
    __tablename__ = 'nodes'

    service = Column(String(30), primary_key=True, nullable=False)
    node = Column(String(64), primary_key=True, nullable=False)

    available = Column(Integer(11), default=0, nullable=False)
    current_load = Column(Integer(11), default=0, nullable=False)
    capacity = Column(Integer(11), default=0, nullable=False)
    downed = Column(Integer(6), default=0, nullable=False)
    backoff = Column(Integer(11), default=0, nullable=False)


nodes = Nodes.__table__
tables.append(nodes)



_GET = sqltext("""\
select
    uid, node
from
    user_nodes
where
    email = :email
and
    service = :service
""")


_INSERT = sqltext("""\
insert into user_nodes
    (service, email, node)
values
    (:service, :email, :node)
""")


WRITEABLE_FIELDS = ['available', 'current_load', 'capacity', 'downed',
                    'backoff']



class SQLNodeAssignment(object):
    implements(INodeAssignment)

    def __init__(self, sqluri, create_tables=False, **kw):
        self.sqluri = sqluri
        self._engine = create_engine(sqluri, poolclass=NullPool)
        self.user_nodes = get_user_nodes_table(self._engine.driver)

        for table in tables + [self.user_nodes]:
            table.metadata.bind = self._engine
            if create_tables:
                table.create(checkfirst=True)

    #
    # Node allocation
    #
    def get_node(self, email, service):
        res = self._safe_execute(_GET, email=email, service=service)
        res = res.fetchone()
        if res is None:
            return None, None
        return res.uid, res.node

    def allocate_node(self, email, service):
        if self.get_node(email, service) != (None, None):
            raise BackendError("Node already assigned")

        # getting a node
        node = self.get_best_node(service)

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
    #
    # Nodes management
    #
    def get_best_node(self, service):
        """Returns the 'least loaded' node currently available, increments the
        active count on that node, and decrements the slots currently available
        """
        where = [nodes.c.service == service,
                 nodes.c.available > 0,
                 nodes.c.capacity > nodes.c.current_load,
                 nodes.c.downed == 0]

        query = select([nodes]).where(and_(*where))
        query = query.order_by(nodes.c.current_load /
                               nodes.c.capacity).limit(1)
        res = self._safe_execute(query)
        res = res.fetchone()
        if res is None:
            # unable to get a node
            raise BackendError('unable to get a node')

        node = str(res.node)
        current_load = int(res.current_load)
        available = int(res.available)
        self.update_node(node, service, available=available-1,
                         current_load=current_load+1)
        return res.node

    def update_node(self, node, service, **fields):
        for field in fields:
            if field not in WRITEABLE_FIELDS:
                raise NotImplementedError()

        where = [nodes.c.service == service, nodes.c.node == node]
        where = and_(*where)
        query = update(nodes, where, fields)
        self._engine.execute(query)
        return True
