""" SQL Mappers
"""
import json
import sys
from zope.interface import implements
import time
import urllib
import urlparse

from mozsvc.util import dnslookup

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
        exc, value, __ = sys.exc_info()
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
        self._resolved = None, time.time()

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
                self.get_logger().error("bad json body from sreg (%s): %s" %
                                                        (url, body))
                raise BackendError('Bad answer from proxy')
        return status, body

    def _dnslookup(self, proxy):
        # does a DNS lookup with gethostbyname and cache it in
        # memory for one hour.
        current, age = self._resolved
        if current is None or age + 3600 < time.time():
            current = dnslookup(proxy)
            self._resolved = current, time.time()

        return current

    def allocate_node(self, email, service):
        """Calls the proxy to get an allocation"""
        proxy_uri = self._dnslookup(self.proxy_uri)
        url = '%s/1.0/%s' % (proxy_uri, service)
        data = {'email': email}
        status, body = self._proxy('POST', url, data)
        if status != 200:
            msg = 'Could not get an allocation\n'
            msg += 'status: %s\n' % status
            msg += 'body: %s\n' % str(body)
            raise BackendError(msg, backend=url)

        return body['uid'], body['node']
