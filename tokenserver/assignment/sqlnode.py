""" SQL Mappers
"""
import json
import sys
from zope.interface import implements

from tokenserver.assignment import INodeAssignment
from tokenserver.util import get_logger

# try to have this changed upstream:
# XXX being able to set autocommit=1;
# forcing it for now
from pymysql.connections import Connection, COM_QUERY


def autocommit(self, value):
    value = True
    try:
        self._execute_command(COM_QUERY, "SET AUTOCOMMIT = %s" % \
                                    self.escape(value))
        self.read_packet()
    except:
        exc,value,tb = sys.exc_info()
        self.errorhandler(None, exc, value)

Connection.autocommit = autocommit


from mozsvc.exceptions import BackendError
from mozsvc.http_helpers import get_url
from wimms.sql import SQLMetadata
from wimms.shardedsql import ShardedSQLMetadata


class SQLNodeAssignment(SQLMetadata):
    """Just a placeholder to mark with a zope interface.

    Silly, isn't it ?
    """
    implements(INodeAssignment)

    def get_patterns(self):
        res = super(SQLNodeAssignment, self).get_patterns()
        return dict([(pattern.service, pattern.pattern) for pattern in res])


class ShardedSQLNodeAssignment(ShardedSQLMetadata):
    """Like the SQL backend, but with one DB per service
    """
    implements(INodeAssignment)


class SecuredShardedSQLNodeAssignment(ShardedSQLMetadata):
    """Like the sharded backend, but proxies all writes to stoken
    """
    implements(INodeAssignment)

    def __init__(self, proxy_uri, databases, create_tables, **kw):
        base = super(SecuredShardedSQLNodeAssignment, self)
        base.__init__(databases, create_tables, **kw)
        self.proxy_uri = proxy_uri
        self.logger = None

    def get_logger(self):
        if self.logger is None:
            self.logger = get_logger()
        return self.logger

    def _proxy(self, method, url, data=None, headers=None):
        if data is not None:
            data = json.dumps(data)
        status, headers, body = get_url(url, method, data, headers)
        if body:
            try:
                body = json.loads(body)
            except ValueError:
                self.logger.error("bad json body from sreg (%s): %s" %
                                                        (url, body))
                raise BackendError('Bad answer from proxy')
        return status, body

    def allocate_node(self, email, service):
        """Calls the proxy to get an allocation"""
        url = '%s/1.0/%s' % (self.proxy_uri, service)
        data = {'email': email}
        status, body = self._proxy('POST', url, data)
        if status != 200:
            raise BackendError('Could not get an allocation')

        return body['uid'], body['node']
