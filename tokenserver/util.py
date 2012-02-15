# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import json
import urlparse
from mozsvc.http_helpers import get_url
from mozsvc.exceptions import BackendError

from tokenserver import logger


class SREGBackend(object):

    def __init__(self, location, path, scheme=None, **kw):
        self.location = location
        self.scheme = scheme
        self.path = path

    def _generate_url(self, username, additional_path=None):
        path = "%s/%s" % (self.path, username)
        if additional_path:
            path = "%s/%s" % (path, additional_path)
        url = urlparse.urlunparse([self.scheme, self.location,
                                  path, None, None, None])
        return url

    def _proxy(self, method, url, data=None, headers=None):
        if data is not None:
            data = json.dumps(data)
        status, headers, body = get_url(url, method, data, headers)
        if body:
            try:
                body = json.loads(body)
            except Exception:
                logger.error("bad json body from sreg (%s): %s" %
                                                        (url, body))
        return status, body

    def create_user(sreg_url, email):
        url = self._generate_url(username)
        payload = {'password': password, 'email': email}
        status, body = self._proxy('PUT', url, payload)
        if status != 200:
            msg = 'Unable to create the user via sreg. '
            msg += 'Received body:\n%s\n' % str(body)
            msg += 'Received status: %d' % status
            raise BackendError(msg, server=url)

        # the result is the username on success
        if body == username:
            return username

        msg = 'Unable to create the user via sreg. '
        msg += 'Received body:\n%s\n' % str(body)
        msg += 'Received status: %d' % status
        raise BackendError(msg, server=url)
