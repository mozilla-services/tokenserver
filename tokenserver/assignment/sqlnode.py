"""
Node-assignment backend using an SQL database.

This INodeAssignment backend uses the "Where Is My Mozilla Service" project
aka "WIMMS" to implement the storage backend.  WIMMS provides a bunch of
management infrastructure atop an SQL database.
"""

import json
import time

from zope.interface import implements

import requests

from mozsvc.util import dnslookup

from tokenserver.assignment import INodeAssignment
from tokenserver.util import get_logger

from mozsvc.exceptions import BackendError

from wimms.sql import SQLMetadata
from wimms.shardedsql import ShardedSQLMetadata


PROXY_API_VERSION = "1.0"


class SQLNodeAssignment(SQLMetadata):
    """Wrap the WIMMS sql implementation in an INodeAssignment."""
    implements(INodeAssignment)

    def get_patterns(self):
        res = super(SQLNodeAssignment, self).get_patterns()
        return dict([(pattern.service, pattern.pattern) for pattern in res])


class ShardedSQLNodeAssignment(ShardedSQLMetadata):
    """Wrap the WIMMS sharded sql implementation in an INodeAssignment.

    This is just like the SQLNodeAssignment backend, but it transparently
    uses a different user database of each service.
    """
    implements(INodeAssignment)

    def get_patterns(self):
        res = super(SQLNodeAssignment, self).get_patterns()
        return dict([(pattern.service, pattern.pattern) for pattern in res])


class SecuredShardedSQLNodeAssignment(ShardedSQLNodeAssignment):
    """Wraps the WIMMS shareded sql implement with a http write proxy.

    This is just like the ShardedSQLNodeAssignment backend, but all writes are
    proxied to a secure service via https.  Handy for keeping database write
    credentials off of publicly-accessible machines.
    """

    def __init__(self, proxy_uri, *args, **kw):
        super(SecuredShardedSQLNodeAssignment, self).__init__(*args, **kw)
        self.proxy_uri = proxy_uri
        self.logger = None
        self._resolved_uri = None, time.time()

    def get_logger(self):
        if self.logger is None:
            self.logger = get_logger()
        return self.logger

    def _proxy_request(self, method, path, data=None, headers=None):
        url = self._dnslookup(self.proxy_uri)
        url = url + "/" + PROXY_API_VERSION + "/" + path
        if data is not None:
            data = json.dumps(data)

        try:
            resp = requests.request(method, url, data=data, headers=headers)
        except requests.exceptions.RequestException:
            self.get_logger().exception("error talking to sreg (%s)" % (url,))
            raise BackendError('Error talking to proxy')

        if resp.status_code != 200:
            msg = 'node allocation backend failure\n'
            msg += 'status: %s\n' % resp.status_code
            msg += 'body: %s\n' % resp.content
            raise BackendError(msg, backend=url)

        body = resp.content
        if body:
            try:
                body = json.loads(body)
            except ValueError:
                self.get_logger().error("bad json body from sreg (%s): %s" %
                                        (url, body))
                raise BackendError('Bad answer from proxy')
        return body

    def _dnslookup(self, proxy):
        # does a DNS lookup with gethostbyname
        # and caches it in memory for one hour.
        now = time.time()
        current, age = self._resolved_uri
        if current is None or age + 3600 < now:
            current = dnslookup(proxy)
            self._resolved_uri = current, now
        return current

    def create_user(self, service, email, generation=0, client_state=''):
        """Calls the proxy to create a new user record."""
        body = self._proxy('POST', service, {
            'email': email,
            'generation': generation,
            'client_state': client_state,
        })
        return body

    def update_user(self, service, user, generation=None, client_state=None):
        """Calls the proxy to update an existing user record."""
        # Actually this is just the same API as create_user.
        email = user['email']
        return self.create_user(service, email, generation, client_state)
