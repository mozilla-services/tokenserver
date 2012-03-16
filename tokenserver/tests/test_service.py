# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from webtest import TestApp
import unittest
import json
import os
from pyramid import testing

from vep.tests.support import (
    patched_urlopen,
    fetch_public_key,
    make_assertion
)

from cornice.tests import CatchErrors
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register
from tokenserver.assignment import INodeAssignment


here = os.path.dirname(__file__)


class TestService(unittest.TestCase):

    def get_ini(self):
        return os.path.join(os.path.dirname(__file__),
                            'test_fixednode.ini')

    def setUp(self):
        self.config = testing.setUp()
        settings = {}
        load_into_settings(self.get_ini(), settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")
        load_and_register("tokenserver", self.config)
        self.backend = self.config.registry.getUtility(INodeAssignment)
        wsgiapp = self.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)

        def urlopen(url, data): # NOQA
            class response(object):
                @staticmethod
                def read():
                    key = fetch_public_key("browserid.org")
                    return json.dumps({"public-key": key})
            return response

        self.patched = patched_urlopen(urlopen)
        self.patched.__enter__()

    def tearDown(self):
        self.patched.__exit__(None, None, None)

    def _getassertion(self):
        email = 'tarek@mozilla.com'
        url = 'http://tokenserver.services.mozilla.com'
        return make_assertion(email, url)

    def test_unknown_app(self):
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        resp = self.app.get('/1.0/xXx/token', headers=headers, status=404)
        self.assertTrue('errors' in resp.json)

    def test_no_auth(self):
        self.app.get('/1.0/sync/2.1', status=401)

    def test_valid_app(self):
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        res = self.app.get('/1.0/sync/2.1', headers=headers)
        self.assertEqual(res.json['service_entry'], 'example.com')

    def test_discovery(self):
        res = self.app.get('/')
        self.assertEqual(res.json['auth'],
                         'https://token.services.mozilla.com')
