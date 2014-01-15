# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import json
import time

from webtest import TestApp
from pyramid import testing

from cornice.tests.support import CatchErrors
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register, load_from_settings

from metlog.logging import hook_logger

from tokenserver.assignment import INodeAssignment
from browserid.tests.support import (
    make_assertion,
    patched_supportdoc_fetching,
    unittest
)


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
        metlog_wrapper = load_from_settings('metlog',
                self.config.registry.settings)
        for logger in ('tokenserver', 'mozsvc', 'powerhose'):
            hook_logger(logger, metlog_wrapper.client)

        self.config.registry['metlog'] = metlog_wrapper.client
        self.config.include("tokenserver")
        load_and_register("tokenserver", self.config)
        self.backend = self.config.registry.getUtility(INodeAssignment)
        wsgiapp = self.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)

        self.patched = patched_supportdoc_fetching()
        self.patched.__enter__()

        # by default the conditions are accepted
        self.backend.set_accepted_conditions_flag('aitc-1.0', True)

    def tearDown(self):
        self.patched.__exit__(None, None, None)

    def _getassertion(self, **kw):
        kw.setdefault('email', 'tarek@mozilla.com')
        kw.setdefault('audience', 'http://tokenserver.services.mozilla.com')
        return make_assertion(**kw).encode('ascii')

    def test_unknown_app(self):
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        resp = self.app.get('/1.0/xXx/token', headers=headers, status=404)
        self.assertTrue('errors' in resp.json)

    def test_no_auth(self):
        self.app.get('/1.0/sync/2.1', status=401)

    def test_valid_app(self):
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        res = self.app.get('/1.0/aitc/1.0', headers=headers)
        self.assertIn('https://example.com/1.0', res.json['api_endpoint'])
        self.assertIn('duration', res.json)
        self.assertEquals(res.json['duration'], 3600)

    def test_unknown_pattern(self):
        # sync 2.1 is defined in the .ini file, but  no pattern exists for it.
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        self.app.get('/1.0/sync/2.1', headers=headers, status=503)

    def test_discovery(self):
        res = self.app.get('/')
        self.assertEqual(res.json['auth'],
                         'https://token.services.mozilla.com')

    def test_tos_signed(self):
        # preparing the data
        self.backend.set_accepted_conditions_flag('aitc-1.0', False)
        self.backend.set_metadata('aitc-1.0', 'tos', 'http://tos',
                                   needs_acceptance=True)
        self.backend.set_metadata('aitc-1.0', 'pp', 'http://pp',
                                   needs_acceptance=True)
        self.backend.set_metadata('aitc-1.0', 'boo', 'http://boo')

        # let's call as usual, we should get a 403
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        res = self.app.get('/1.0/aitc/1.0', headers=headers, status=403)

        errors = res.json['errors']
        self.assertEqual(len(errors), 1)
        error = errors[0]

        self.assertEqual(error['location'], 'header')
        self.assertEqual(error['name'], 'X-Conditions-Accepted')

        urls = error['condition_urls']
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls['tos'], 'http://tos')
        self.assertEqual(urls['pp'], 'http://pp')

        # let's sign the urls !
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion(),
                   'X-Conditions-Accepted': '1'}
        res = self.app.get('/1.0/aitc/1.0', headers=headers)
        self.assertIn('https://example.com/1.0', res.json['api_endpoint'])
        self.assertIn('duration', res.json)
        self.assertEquals(res.json['duration'], 3600)

    def test_stats_capture(self):
        # make a simple request
        res = self.app.get('/')
        self.assertEqual(res.json['auth'],
                         'https://token.services.mozilla.com')
        msgs = self.config.registry['metlog'].sender.msgs

        def is_in_msgs(subset):
            subset_items = subset.items()
            for msg in msgs:
                msg_items = json.loads(msg).items()
                match = all(item in msg_items for item in subset_items)
                if match:
                    return True
            return False

        fields = {'rate': 1.0, 'name': 'tokenserver.views._discovery'}
        timer_subset = {'type': 'timer',
                        'fields': fields,
                        }
        self.assertTrue(is_in_msgs(timer_subset))
        counter_subset = {'type': 'counter',
                          'fields': fields,
                        }
        self.assertTrue(is_in_msgs(counter_subset))

    def test_unauthorized_error_status(self):
        # Totally busted auth -> generic error.
        headers = {'Authorization': 'Unsupported-Auth-Scheme IHACKYOU'}
        res = self.app.get('/1.0/aitc/1.0', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'error')
        # Bad signature -> "invalid-credentials" 
        assertion = self._getassertion(assertion_sig='IHACKYOU')
        headers = {'Authorization': 'Browser-ID %s' % assertion}
        res = self.app.get('/1.0/aitc/1.0', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        # Bad audience -> "invalid-credentials" 
        assertion = self._getassertion(audience='http://i.hackyou.com')
        headers = {'Authorization': 'Browser-ID %s' % assertion}
        res = self.app.get('/1.0/aitc/1.0', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        # Expired timestamp -> "invalid-timestamp" 
        assertion = self._getassertion(exp=42)
        headers = {'Authorization': 'Browser-ID %s' % assertion}
        res = self.app.get('/1.0/aitc/1.0', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-timestamp')
        self.assertTrue('X-Timestamp' in res.headers)
        # Far-future timestamp -> "invalid-timestamp" 
        assertion = self._getassertion(exp=int(time.time() + 3600))
        headers = {'Authorization': 'Browser-ID %s' % assertion}
        res = self.app.get('/1.0/aitc/1.0', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-timestamp')
        self.assertTrue('X-Timestamp' in res.headers)
