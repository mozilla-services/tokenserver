# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import unittest
import json
import urllib2

from tokenserver.util import SREGBackend


class _Resp(object):
    def __init__(self, data='', code=200):
        self.data = data
        self.code = code
        self.headers = {}

    def read(self):
        return self.data

    def getcode(self):
        return self.code


class TestSREG(unittest.TestCase):
    def setUp(self):
        self.old = urllib2.urlopen
        urllib2.urlopen = self._response

    def tearDown(self):
        urllib2.urlopen = self.old

    def _response(self, *args, **kw):
        return _Resp(json.dumps('kismw365lo7emoxr3ohojgpild6lph4b'))

    def test_backend(self):
        # let's create a user
        backend = SREGBackend('example.com', '/1.0/sreg')
        username = backend.create_user('john@example.com')
        self.assertEquals(username, 'kismw365lo7emoxr3ohojgpild6lph4b')
