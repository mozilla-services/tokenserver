""" SQL Mappers
"""
import json
from zope.interface import implements

from tokenserver.assignment import INodeAssignment
from tokenserver import logger

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
        patterns = super(SQLNodeAssignment, self).get_patterns()
        return dict([((service, version), pattern)
                    for service, version, pattern in patterns])


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

    def _proxy(self, method, url, data=None, headers=None):
        if data is not None:
            data = json.dumps(data)
        status, headers, body = get_url(url, method, data, headers)
        if body:
            try:
                body = json.loads(body)
            except ValueError:
                logger.error("bad json body from sreg (%s): %s" %
                                                        (url, body))
                raise BackendError('Bad answer from proxy')
        return status, body

    def allocate_node(self, email, service):
        """Calls the proxy to get an allocation"""
        url = '%s/1.0/%s' % (self.proxy_uri, service)
        data = json.dumps({'email': email})
        status, body = self._proxy('POST', url, data)
        if status != 200:
            raise BackendError('Could not get an allocation')

        return data['uid'], data['node']
