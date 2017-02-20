# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import contextlib
import json
import os
import mock

from webtest import TestApp
from pyramid import testing
from testfixtures import LogCapture

from cornice.tests.support import CatchErrors
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver.assignment import INodeAssignment
from tokenserver.verifiers import get_verifier
from tokenserver.tests.support import unittest

import browserid.errors
from browserid.tests.support import make_assertion
from browserid.utils import get_assertion_info


here = os.path.dirname(__file__)


class TestService(unittest.TestCase):

    def get_ini(self):
        return os.path.join(os.path.dirname(__file__),
                            'test_memorynode.ini')

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
        # Mock out the verifier to return successfully by default.
        self.mock_verifier_context = self.mock_verifier()
        self.mock_verifier_context.__enter__()
        self.logs = LogCapture()

    def tearDown(self):
        self.logs.uninstall()
        self.mock_verifier_context.__exit__(None, None, None)

    def assertMetricWasLogged(self, key):
        """Check that a metric was logged during the request."""
        for r in self.logs.records:
            if key in r.__dict__:
                break
        else:
            assert False, "metric %r was not logged" % (key,)

    def clearLogs(self):
        del self.logs.records[:]

    @contextlib.contextmanager
    def mock_verifier(self, response=None, exc=None):
        def mock_verify_method(assertion):
            if exc is not None:
                raise exc
            if response is not None:
                return response
            return {
                "status": "okay",
                "email": get_assertion_info(assertion)["principal"]["email"],
            }
        verifier = get_verifier(self.config.registry)
        orig_verify_method = verifier.__dict__.get("verify", None)
        verifier.__dict__["verify"] = mock_verify_method
        try:
            yield None
        finally:
            if orig_verify_method is None:
                del verifier.__dict__["verify"]
            else:
                verifier.__dict__["verify"] = orig_verify_method

    def _getassertion(self, **kw):
        kw.setdefault('email', 'tarek@mozilla.com')
        kw.setdefault('audience', 'http://tokenserver.services.mozilla.com')
        return make_assertion(**kw).encode('ascii')

    def test_unknown_app(self):
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        resp = self.app.get('/1.0/xXx/token', headers=headers, status=404)
        self.assertTrue('errors' in resp.json)

    def test_no_auth(self):
        self.app.get('/1.0/sync/1.5', status=401)

    def test_valid_app(self):
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertIn('https://example.com/1.1', res.json['api_endpoint'])
        self.assertIn('duration', res.json)
        self.assertEquals(res.json['duration'], 3600)
        self.assertMetricWasLogged('token.assertion.verify_success')
        self.clearLogs()

    def test_unknown_pattern(self):
        # sync 1.5 is defined in the .ini file, but  no pattern exists for it.
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        self.app.get('/1.0/sync/1.5', headers=headers, status=503)

    def test_discovery(self):
        res = self.app.get('/')
        self.assertEqual(res.json, {
            'auth': 'http://localhost',
            'services': {
                'sync': ['1.1', '1.5'],
            }
        })

    def test_version_returns_404_by_default(self):
        self.app.get('/__version__', status=404)

    def test_version_returns_file_in_current_folder_if_present(self):
        content = {'version': '0.8.1'}
        fake_file = mock.mock_open(read_data=json.dumps(content))
        with mock.patch('os.path.exists'):
            with mock.patch('tokenserver.views.open', fake_file, create=True):
                response = self.app.get('/__version__')
                self.assertEquals(response.json, content)

    def test_lbheartbeat(self):
        res = self.app.get('/__lbheartbeat__')
        self.assertEqual(res.json, {})

    def test_unauthorized_error_status(self):
        assertion = self._getassertion()
        # Totally busted auth -> generic error.
        headers = {'Authorization': 'Unsupported-Auth-Scheme IHACKYOU'}
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'error')
        # Bad signature -> "invalid-credentials"
        headers = {'Authorization': 'BrowserID %s' % assertion}
        with self.mock_verifier(exc=browserid.errors.InvalidSignatureError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        # Bad audience -> "invalid-credentials"
        with self.mock_verifier(exc=browserid.errors.AudienceMismatchError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        self.assertMetricWasLogged('token.assertion.verify_failure')
        self.assertMetricWasLogged('token.assertion.audience_mismatch_error')
        self.clearLogs()
        # Expired timestamp -> "invalid-timestamp"
        with self.mock_verifier(exc=browserid.errors.ExpiredSignatureError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-timestamp')
        self.assertTrue('X-Timestamp' in res.headers)
        self.assertMetricWasLogged('token.assertion.verify_failure')
        self.assertMetricWasLogged('token.assertion.expired_signature_error')
        self.clearLogs()
        # Connection error -> 503
        with self.mock_verifier(exc=browserid.errors.ConnectionError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=503)
        self.assertMetricWasLogged('token.assertion.verify_failure')
        self.assertMetricWasLogged('token.assertion.connection_error')
        # It should also log a full traceback of the error.
        for r in self.logs.records:
            if r.msg == "Unexpected verification error":
                assert r.exc_info is not None
                break
        else:
            assert False, "failed to log a traceback for ConnectionError"
        self.clearLogs()
        # Some other wacky error -> not captured
        with self.mock_verifier(exc=ValueError):
            with self.assertRaises(ValueError):
                res = self.app.get('/1.0/sync/1.1', headers=headers)

    def test_unverified_token(self):
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        # Assertion should not be rejected if fxa-tokenVerified is unset
        mock_response = {
            "status": "okay",
            "email": "test@mozilla.com",
            "idpClaims": {}
        }
        with self.mock_verifier(response=mock_response):
            self.app.get("/1.0/sync/1.1", headers=headers, status=200)
        # Assertion should not be rejected if fxa-tokenVerified is True
        mock_response['idpClaims']['fxa-tokenVerified'] = True
        with self.mock_verifier(response=mock_response):
            self.app.get("/1.0/sync/1.1", headers=headers, status=200)
        # Assertion should be rejected if fxa-tokenVerified is False
        mock_response['idpClaims']['fxa-tokenVerified'] = False
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')

    def test_generation_number_change(self):
        headers = {"Authorization": "BrowserID %s" % self._getassertion()}
        # Start with no generation number.
        mock_response = {"status": "okay", "email": "test@mozilla.com"}
        with self.mock_verifier(response=mock_response):
            res1 = self.app.get("/1.0/sync/1.1", headers=headers)
        # Now send an explicit generation number.
        # The node assignment should not change.
        mock_response["idpClaims"] = {"fxa-generation": 12}
        with self.mock_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # Previous generation numbers get an invalid-generation response.
        del mock_response["idpClaims"]
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"some-nonsense": "lolwut"}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": 10}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        # Equal generation numbers are accepted.
        mock_response["idpClaims"] = {"fxa-generation": 12}
        with self.mock_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # Later generation numbers are accepted.
        # Again, the node assignment should not change.
        mock_response["idpClaims"] = {"fxa-generation": 13}
        with self.mock_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # And that should lock out the previous generation number
        mock_response["idpClaims"] = {"fxa-generation": 12}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        # Various nonsense generation numbers should give errors.
        mock_response["idpClaims"] = {"fxa-generation": "whatswrongwithyour"}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": None}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": "42"}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": ["I", "HACK", "YOU"]}
        with self.mock_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")

    def test_client_state_change(self):
        mock_response = {
            "status": "okay",
            "email": "test@mozilla.com",
            "idpClaims": {"fxa-generation": 1234},
        }
        # Start with no client-state header.
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid0 = res.json['uid']
        # No change == same uid.
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid0)
        # Changing client-state header requires changing generation number.
        headers['X-Client-State'] = 'aaaa'
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('new value with no generation change'))
        # Change the client-state header, get a new uid.
        headers['X-Client-State'] = 'aaaa'
        mock_response["idpClaims"]["fxa-generation"] += 1
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid1 = res.json['uid']
        self.assertNotEqual(uid1, uid0)
        # No change == same uid.
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid1)
        # Send a client-state header, get a new uid.
        headers['X-Client-State'] = 'bbbb'
        mock_response["idpClaims"]["fxa-generation"] += 1
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid2 = res.json['uid']
        self.assertNotEqual(uid2, uid0)
        self.assertNotEqual(uid2, uid1)
        # No change == same uid.
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid2)
        # Use a previous client-state, get an auth error.
        headers['X-Client-State'] = 'aaaa'
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('stale value'))
        del headers['X-Client-State']
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        headers['X-Client-State'] = 'aaaa'
        mock_response["idpClaims"]["fxa-generation"] += 1
        with self.mock_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')

    def test_client_state_cannot_revert_to_empty(self):
        # Start with a client-state header.
        headers = {
            'Authorization': 'BrowserID %s' % self._getassertion(),
            'X-Client-State': 'aaa',
        }
        res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid0 = res.json['uid']
        # Sending no client-state will fail.
        del headers['X-Client-State']
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('empty string'))
        headers['X-Client-State'] = ''
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('empty string'))
        # And the uid will be unchanged.
        headers['X-Client-State'] = 'aaa'
        res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid0)

    def test_client_specified_duration(self):
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        # It's ok to request a shorter-duration token.
        res = self.app.get('/1.0/sync/1.1?duration=12', headers=headers)
        self.assertEquals(res.json['duration'], 12)
        # But you can't exceed the server's default value.
        res = self.app.get('/1.0/sync/1.1?duration=4000', headers=headers)
        self.assertEquals(res.json['duration'], 3600)
        # And nonsense values are ignored.
        res = self.app.get('/1.0/sync/1.1?duration=lolwut', headers=headers)
        self.assertEquals(res.json['duration'], 3600)
        res = self.app.get('/1.0/sync/1.1?duration=-1', headers=headers)
        self.assertEquals(res.json['duration'], 3600)

    def test_allow_new_users(self):
        # New users are allowed by default.
        settings = self.config.registry.settings
        self.assertEquals(settings.get('tokenserver.allow_new_users'), None)
        assertion = self._getassertion(email="newuser1@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        # They're allowed if we explicitly allow them.
        settings['tokenserver.allow_new_users'] = True
        assertion = self._getassertion(email="newuser2@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        # They're not allowed if we explicitly disable them.
        settings['tokenserver.allow_new_users'] = False
        assertion = self._getassertion(email="newuser3@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        # But existing users are still allowed.
        assertion = self._getassertion(email="newuser1@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        assertion = self._getassertion(email="newuser2@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        self.app.get('/1.0/sync/1.1', headers=headers, status=200)

    def test_metrics_uid_logging(self):
        assert "fxa.metrics_uid_secret_key" in self.config.registry.settings
        assertion = self._getassertion(email="newuser2@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        self.assertMetricWasLogged('uid')
        self.assertMetricWasLogged('uid.first_seen_at')

    def test_metrics_uid_is_returned_in_response(self):
        assert "fxa.metrics_uid_secret_key" in self.config.registry.settings
        assertion = self._getassertion(email="newuser2@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        self.assertTrue('hashed_fxa_uid' in res.json)
