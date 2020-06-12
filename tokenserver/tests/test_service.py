# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import contextlib
import json
import os
import mock
import unittest

from webtest import TestApp
from pyramid import testing
from testfixtures import LogCapture

from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

import tokenserver.views
from tokenserver.assignment import INodeAssignment
from tokenserver.verifiers import (
    get_browserid_verifier,
    get_oauth_verifier
)

import fxa.errors
import browserid.errors
from browserid.tests.support import make_assertion
from browserid.utils import get_assertion_info

from tokenlib.utils import decode_token_bytes

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
        self.app = TestApp(wsgiapp)
        # Mock out the verifier to return successfully by default.
        self.mock_browserid_verifier_context = self.mock_browserid_verifier()
        self.mock_browserid_verifier_context.__enter__()
        self.mock_oauth_verifier_context = self.mock_oauth_verifier()
        self.mock_oauth_verifier_context.__enter__()
        self.logs = LogCapture()

    def tearDown(self):
        self.logs.uninstall()
        self.mock_oauth_verifier_context.__exit__(None, None, None)
        self.mock_browserid_verifier_context.__exit__(None, None, None)

    def assertExceptionWasLogged(self, msg):
        for r in self.logs.records:
            if r.msg == msg:
                assert r.exc_info is not None
                break
        else:
            assert False, "exception with message %r was not logged" % (msg,)

    def assertMessageWasNotLogged(self, msg):
        for r in self.logs.records:
            if r.msg == msg:
                assert False, "message %r was unexpectedly logged" % (msg,)

    def assertMetricWasLogged(self, key):
        """Check that a metric was logged during the request."""
        for r in self.logs.records:
            if key in r.__dict__:
                break
        else:
            assert False, "metric %r was not logged" % (key,)

    def clearLogs(self):
        del self.logs.records[:]

    def unsafelyParseToken(self, token):
        # For testing purposes, don't check HMAC or anything...
        token = token.encode("utf8")
        return json.loads(decode_token_bytes(token)[:-32].decode("utf8"))

    @contextlib.contextmanager
    def mock_browserid_verifier(self, response=None, exc=None):
        def mock_verify_method(assertion):
            if exc is not None:
                raise exc
            if response is not None:
                return response
            return {
                "status": "okay",
                "email": get_assertion_info(assertion)["principal"]["email"],
            }
        verifier = get_browserid_verifier(self.config.registry)
        orig_verify_method = verifier.__dict__.get("verify", None)
        verifier.__dict__["verify"] = mock_verify_method
        try:
            yield None
        finally:
            if orig_verify_method is None:
                del verifier.__dict__["verify"]
            else:
                verifier.__dict__["verify"] = orig_verify_method

    @contextlib.contextmanager
    def mock_oauth_verifier(self, response=None, exc=None):
        def mock_verify_method(token):
            if exc is not None:
                raise exc
            if response is not None:
                return response
            return {
                "email": token.decode("hex"),
                "idpClaims": {},
            }
        verifier = get_oauth_verifier(self.config.registry)
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
        kw.setdefault('email', 'test1@example.com')
        kw.setdefault('audience', 'http://tokenserver.services.mozilla.com')
        return make_assertion(**kw).encode('ascii')

    def _gettoken(self, email='test1@example.com'):
        return email.encode('hex')

    def test_unknown_app(self):
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        resp = self.app.get('/1.0/xXx/token', headers=headers, status=404)
        self.assertTrue('errors' in resp.json)

    def test_invalid_client_state(self):
        headers = {'X-Client-State': 'state!'}
        resp = self.app.get('/1.0/sync/1.5', headers=headers, status=400)
        self.assertEquals(resp.json['errors'][0]['location'], 'header')
        self.assertEquals(resp.json['errors'][0]['name'], 'X-Client-State')
        headers = {'X-Client-State': 'foobar\n\r\t'}
        resp = self.app.get('/1.0/sync/1.5', headers=headers, status=400)
        self.assertEquals(resp.json['errors'][0]['location'], 'header')
        self.assertEquals(resp.json['errors'][0]['name'], 'X-Client-State')

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
            },
            'browserid': {
                'allowed_issuers': None,
                'trusted_issuers': None,
            },
            'oauth': {
                'default_issuer': 'api.accounts.firefox.com',
                'scope': 'https://identity.mozilla.com/apps/oldsync',
                'server_url': 'https://oauth.accounts.firefox.com/v1',
            }
        })

    def test_version_returns_404_by_default(self):
        # clear cache
        try:
            del tokenserver.views.version_view.__json__
        except AttributeError:
            pass
        with mock.patch('os.path.exists', return_value=False):
            self.app.get('/__version__', status=404)

    def test_version_returns_file_in_current_folder_if_present(self):
        # clear cache
        try:
            del tokenserver.views.version_view.__json__
        except AttributeError:
            pass
        content = {'version': '0.8.1'}
        fake_file = mock.mock_open(read_data=json.dumps(content))
        with mock.patch('os.path.exists'):
            with mock.patch('tokenserver.views.open', fake_file):
                response = self.app.get('/__version__')
                self.assertEquals(response.json, content)

    def test_lbheartbeat(self):
        res = self.app.get('/__lbheartbeat__')
        self.assertEqual(res.json, {})

    def test_unauthorized_error_status(self):
        # Totally busted auth -> generic error.
        headers = {'Authorization': 'Unsupported-Auth-Scheme IHACKYOU'}
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'error')

        # BrowserID verifier errors
        assertion = self._getassertion()
        headers = {'Authorization': 'BrowserID %s' % assertion}
        # Bad signature -> "invalid-credentials"
        errs = browserid.errors
        with self.mock_browserid_verifier(exc=errs.InvalidSignatureError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        # Bad audience -> "invalid-credentials"
        with self.mock_browserid_verifier(exc=errs.AudienceMismatchError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        self.assertMetricWasLogged('token.assertion.verify_failure')
        self.assertMetricWasLogged('token.assertion.audience_mismatch_error')
        self.clearLogs()
        # Expired timestamp -> "invalid-timestamp"
        with self.mock_browserid_verifier(exc=errs.ExpiredSignatureError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-timestamp')
        self.assertTrue('X-Timestamp' in res.headers)
        self.assertMetricWasLogged('token.assertion.verify_failure')
        self.assertMetricWasLogged('token.assertion.expired_signature_error')
        self.clearLogs()
        # Connection error -> 503
        with self.mock_browserid_verifier(exc=errs.ConnectionError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=503)
        self.assertMetricWasLogged('token.assertion.verify_failure')
        self.assertMetricWasLogged('token.assertion.connection_error')
        self.assertExceptionWasLogged('Unexpected verification error')
        self.clearLogs()
        # Some other wacky error -> not captured
        with self.mock_browserid_verifier(exc=ValueError):
            with self.assertRaises(ValueError):
                res = self.app.get('/1.0/sync/1.1', headers=headers)

        # OAuth verifier errors
        token = self._gettoken()
        headers = {'Authorization': 'Bearer %s' % token}
        # Bad token -> "invalid-credentials"
        err = fxa.errors.ClientError({"code": 400, "errno": 108})
        with self.mock_oauth_verifier(exc=err):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        self.assertMetricWasLogged('token.oauth.errno.108')
        self.assertMessageWasNotLogged('Unexpected verification error')
        # Untrusted scopes -> "invalid-credentials"
        err = fxa.errors.TrustError({"code": 400, "errno": 999})
        with self.mock_oauth_verifier(exc=err):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')
        self.assertMessageWasNotLogged('Unexpected verification error')
        # Connection error -> 503
        with self.mock_oauth_verifier(exc=errs.ConnectionError):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=503)
        self.assertMetricWasLogged('token.oauth.verify_failure')
        self.assertMetricWasLogged('token.oauth.connection_error')
        self.assertExceptionWasLogged('Unexpected verification error')
        self.clearLogs()
        # Some other wacky error -> not captured
        with self.mock_oauth_verifier(exc=ValueError):
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
        with self.mock_browserid_verifier(response=mock_response):
            self.app.get("/1.0/sync/1.1", headers=headers, status=200)
        # Assertion should not be rejected if fxa-tokenVerified is True
        mock_response['idpClaims']['fxa-tokenVerified'] = True
        with self.mock_browserid_verifier(response=mock_response):
            self.app.get("/1.0/sync/1.1", headers=headers, status=200)
        # Assertion should be rejected if fxa-tokenVerified is False
        mock_response['idpClaims']['fxa-tokenVerified'] = False
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')

    def test_generation_number_change(self):
        headers = {"Authorization": "BrowserID %s" % self._getassertion()}
        # Start with no generation number.
        mock_response = {"status": "okay", "email": "test@mozilla.com"}
        with self.mock_browserid_verifier(response=mock_response):
            res1 = self.app.get("/1.0/sync/1.1", headers=headers)
        # Now send an explicit generation number.
        # The node assignment should not change.
        mock_response["idpClaims"] = {"fxa-generation": 12}
        with self.mock_browserid_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # Clients that don't report generation number are still allowed.
        del mock_response["idpClaims"]
        with self.mock_browserid_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        mock_response["idpClaims"] = {"some-nonsense": "lolwut"}
        with self.mock_browserid_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        # But previous generation numbers get an invalid-generation response.
        mock_response["idpClaims"] = {"fxa-generation": 10}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        # Equal generation numbers are accepted.
        mock_response["idpClaims"] = {"fxa-generation": 12}
        with self.mock_browserid_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # Later generation numbers are accepted.
        # Again, the node assignment should not change.
        mock_response["idpClaims"] = {"fxa-generation": 13}
        with self.mock_browserid_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers)
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # And that should lock out the previous generation number
        mock_response["idpClaims"] = {"fxa-generation": 12}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        # Various nonsense generation numbers should give errors.
        mock_response["idpClaims"] = {"fxa-generation": "whatswrongwithyour"}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": None}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": "42"}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")
        mock_response["idpClaims"] = {"fxa-generation": ["I", "HACK", "YOU"]}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-generation")

    def test_client_state_change(self):
        mock_response = {
            "status": "okay",
            "email": "test@mozilla.com",
            "idpClaims": {"fxa-generation": 1234, "fxa-keysChangedAt": 1234},
        }
        # Start with no client-state header.
        headers = {'Authorization': 'BrowserID %s' % self._getassertion()}
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid0 = res.json['uid']
        # No change == same uid.
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid0)
        # Changing client-state header requires changing generation.
        headers['X-Client-State'] = 'aaaa'
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('new value with no generation change'))
        # Changing client-state header requires changing keys_changed_at.
        mock_response["idpClaims"]["fxa-generation"] += 1
        headers['X-Client-State'] = 'aaaa'
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('with no keys_changed_at change'))
        # Change the client-state header, get a new uid.
        mock_response["idpClaims"]["fxa-keysChangedAt"] += 1
        headers['X-Client-State'] = 'aaaa'
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid1 = res.json['uid']
        self.assertNotEqual(uid1, uid0)
        # No change == same uid.
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid1)
        # Send a client-state header, get a new uid.
        headers['X-Client-State'] = 'bbbb'
        mock_response["idpClaims"]["fxa-generation"] += 1
        mock_response["idpClaims"]["fxa-keysChangedAt"] += 1
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        uid2 = res.json['uid']
        self.assertNotEqual(uid2, uid0)
        self.assertNotEqual(uid2, uid1)
        # No change == same uid.
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid2)
        # Use a previous client-state, get an auth error.
        headers['X-Client-State'] = 'aaaa'
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        desc = res.json['errors'][0]['description']
        self.assertTrue(desc.endswith('stale value'))
        del headers['X-Client-State']
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')
        headers['X-Client-State'] = 'aaaa'
        mock_response["idpClaims"]["fxa-generation"] += 1
        mock_response["idpClaims"]["fxa-keysChangedAt"] += 1
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json['status'], 'invalid-client-state')

    def test_fxa_kid_change(self):
        # Starting off not reporting keys_changed_at.
        # We don't expect to encounter this in production, but it might
        # happen to self-hosters who update tokenserver without updating
        # their FxA stack.
        headers = {
            "Authorization": "BrowserID %s" % self._getassertion(),
            "X-Client-State": "616161",
        }
        mock_response = {
            "status": "okay",
            "email": "test@mozilla.com",
            "idpClaims": {"fxa-generation": 1234},
        }
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000001234-YWFh")
        # Now pretend we updated FxA and it started sending keys_changed_at.
        mock_response["idpClaims"]["fxa-generation"] = 2345
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 2345
        headers["X-Client-State"] = "626262"
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000002345-YmJi")
        # If we roll back the FxA stack so it stops reporting keys_changed_at,
        # users will get locked out because we can't produce `fxa_kid`.
        del mock_response["idpClaims"]["fxa-keysChangedAt"]
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-keysChangedAt")
        # We will likewise reject values below the high-water mark.
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 2340
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        self.assertEqual(res.json["status"], "invalid-keysChangedAt")
        # But accept the correct value, even if generation number changes.
        mock_response["idpClaims"]["fxa-generation"] = 3456
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 2345
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000002345-YmJi")
        # TODO: ideally we will error if keysChangedAt changes without a
        # change in generation, but we can't do that until all servers
        # are running the latest version of the code.
        # mock_response["idpClaims"]["fxa-keysChangedAt"] = 4567
        # headers["X-Client-State"] = "636363"
        # with self.mock_browserid_verifier(response=mock_response):
        #     res = self.app.get('/1.0/sync/1.1', headers=headers, status=401)
        # self.assertEqual(res.json["status"], "invalid-keysChangedAt")
        # But accept further updates if both values change in unison.
        mock_response["idpClaims"]["fxa-generation"] = 4567
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 4567
        headers["X-Client-State"] = "636363"
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000004567-Y2Nj")

    def test_fxa_kid_change_with_oauth(self):
        # Starting off not reporting keys_changed_at.
        # This uses BrowserID since OAuth always reports keys_changed_at.
        headers_browserid = {
            "Authorization": "BrowserID %s" % self._getassertion(),
            "X-Client-State": "616161",
        }
        mock_response = {
            "status": "okay",
            "email": "test@mozilla.com",
            "idpClaims": {"fxa-generation": 1234},
        }
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers_browserid)
        token0 = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token0["fxa_kid"], "0000000001234-YWFh")
        # Now an OAuth client shows up, setting keys_changed_at.
        # (The value matches generation number above, beause in this scenario
        # FxA hasn't been updated to track and report keysChangedAt yet).
        headers_oauth = {
            "Authorization": "Bearer %s" % self._gettoken("test@mozilla.com"),
            "X-KeyID": "1234-YWFh",
        }
        res = self.app.get('/1.0/sync/1.1', headers=headers_oauth)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000001234-YWFh")
        self.assertEqual(token["uid"], token0["uid"])
        self.assertEqual(token["node"], token0["node"])
        # At this point, BrowserID clients are locked out until FxA is updated,
        # because we're now expecting to see keys_changed_at for that user.
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers_browserid,
                               status=401)
        self.assertEqual(res.json["status"], "invalid-keysChangedAt")
        # We will likewise reject values below the high-water mark.
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 1230
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers_browserid,
                               status=401)
        self.assertEqual(res.json["status"], "invalid-keysChangedAt")
        headers_oauth["X-KeyID"] = "1230-YWFh"
        res = self.app.get('/1.0/sync/1.1', headers=headers_oauth, status=401)
        self.assertEqual(res.json["status"], "invalid-keysChangedAt")
        # We accept new values via OAuth.
        headers_oauth["X-KeyID"] = "2345-YmJi"
        res = self.app.get('/1.0/sync/1.1', headers=headers_oauth)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000002345-YmJi")
        self.assertNotEqual(token["uid"], token0["uid"])
        self.assertEqual(token["node"], token0["node"])
        # And via BrowserID, as long as generation number increases as well.
        headers_browserid["X-Client-State"] = "636363"
        mock_response["idpClaims"]["fxa-generation"] = 3456
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 3456
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers_browserid)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000003456-Y2Nj")

    def test_kid_change_during_gradual_tokenserver_rollout(self):
        # Let's start with a user already in the db, with no keys_changed_at.
        user0 = self.backend.allocate_user("sync-1.1", "test@mozilla.com",
                                           generation=1234,
                                           client_state="616161")
        # User hits updated tokenserver node, writing keys_changed_at to db.
        headers = {
            "Authorization": "BrowserID %s" % self._getassertion(),
            "X-Client-State": "616161",
        }
        mock_response = {
            "status": "okay",
            "email": "test@mozilla.com",
            "idpClaims": {
                "fxa-generation": 1234,
                "fxa-keysChangedAt": 1200,
            },
        }
        with self.mock_browserid_verifier(response=mock_response):
            self.app.get('/1.0/sync/1.1', headers=headers)
        # That should not have triggered a node re-assignment.
        user1 = self.backend.get_user("sync-1.1", mock_response["email"])
        self.assertEqual(user1['uid'], user0['uid'])
        self.assertEqual(user1['node'], user0['node'])
        # That should have written keys_changed_at into the db.
        self.assertEqual(user1["generation"], 1234)
        self.assertEqual(user1["keys_changed_at"], 1200)
        # User does a password reset on their Firefox Account.
        mock_response["idpClaims"]["fxa-generation"] = 2345
        mock_response["idpClaims"]["fxa-keysChangedAt"] = 2345
        headers["X-Client-State"] = "626262"
        # They sync again, but hit a tokenserver node that isn't updated yet.
        # Simulate this by writing the updated data directly to the backend,
        # which should trigger a node re-assignment.
        self.backend.update_user("sync-1.1", user1,
                                 generation=2345,
                                 client_state="626262")
        self.assertNotEqual(user1['uid'], user0['uid'])
        self.assertEqual(user1['node'], user0['node'])
        # They sync again, hitting an updated tokenserver node.
        # This should succeed, despite keys_changed_at appearing to have
        # changed without any corresponding change in generation number.
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get('/1.0/sync/1.1', headers=headers)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["fxa_kid"], "0000000002345-YmJi")
        # That should not have triggered a second node re-assignment.
        user2 = self.backend.get_user("sync-1.1", mock_response["email"])
        self.assertEqual(user2['uid'], user1['uid'])
        self.assertEqual(user2['node'], user1['node'])

    def test_client_state_cannot_revert_to_empty(self):
        # Start with a client-state header.
        headers = {
            'Authorization': 'BrowserID %s' % self._getassertion(),
            'X-Client-State': 'aaaa',
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
        headers['X-Client-State'] = 'aaaa'
        res = self.app.get('/1.0/sync/1.1', headers=headers)
        self.assertEqual(res.json['uid'], uid0)

    def test_credentials_from_oauth_and_browserid(self):
        # Send initial credentials via oauth.
        headers_oauth = {
            "Authorization": "Bearer %s" % self._gettoken(),
            "X-KeyID": "7-YWFh",
        }
        res1 = self.app.get("/1.0/sync/1.1", headers=headers_oauth)
        # Send the same credentials via BrowserID
        headers_browserid = {
            "Authorization": "BrowserID %s" % self._getassertion(),
            "X-Client-State": "616161",
        }
        mock_response = {
            "status": "okay",
            "email": "test1@example.com",
            "idpClaims": {"fxa-generation": 12, "fxa-keysChangedAt": 7},
        }
        with self.mock_browserid_verifier(response=mock_response):
            res2 = self.app.get("/1.0/sync/1.1", headers=headers_browserid)
        # They should get the same node assignment.
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        # Earlier generation number via BrowserID -> invalid-generation
        mock_response["idpClaims"]['fxa-generation'] = 11
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers_browserid,
                               status=401)
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])
        self.assertEqual(res.json["status"], "invalid-generation")
        # Earlier keys_changed_at via BrowserID is not accepted.
        mock_response["idpClaims"]['fxa-generation'] = 12
        mock_response["idpClaims"]['fxa-keysChangedAt'] = 6
        with self.mock_browserid_verifier(response=mock_response):
            res1 = self.app.get("/1.0/sync/1.1", headers=headers_browserid,
                                status=401)
        self.assertEqual(res1.json['status'], 'invalid-keysChangedAt')
        # Earlier keys_changed_at via OAuth is not accepted.
        headers_oauth['X-KeyID'] = '6-YWFh'
        res1 = self.app.get("/1.0/sync/1.1", headers=headers_oauth, status=401)
        self.assertEqual(res1.json['status'], 'invalid-keysChangedAt')
        # Change client-state via BrowserID.
        headers_browserid['X-Client-State'] = '626262'
        mock_response["idpClaims"]['fxa-generation'] = 42
        mock_response["idpClaims"]['fxa-keysChangedAt'] = 42
        with self.mock_browserid_verifier(response=mock_response):
            res1 = self.app.get("/1.0/sync/1.1", headers=headers_browserid)
        # Previous OAuth creds are rejected due to keys_changed_at update.
        headers_oauth['X-KeyID'] = '7-YmJi'
        res2 = self.app.get("/1.0/sync/1.1", headers=headers_oauth, status=401)
        self.assertEqual(res2.json['status'], 'invalid-keysChangedAt')
        # Updated OAuth creds are accepted.
        headers_oauth['X-KeyID'] = '42-YmJi'
        res2 = self.app.get("/1.0/sync/1.1", headers=headers_oauth)
        # They should again get the same node assignment.
        self.assertEqual(res1.json["uid"], res2.json["uid"])
        self.assertEqual(res1.json["api_endpoint"], res2.json["api_endpoint"])

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
        self.assertEqual(res.json['status'], 'new-users-disabled')
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
        self.assertMetricWasLogged('metrics_uid')
        self.assertMetricWasLogged('metrics_device_id')

    def test_uid_and_kid_from_browserid_assertion(self):
        assertion = self._getassertion(email="testuser@example.com")
        headers_browserid = {
            "Authorization": "BrowserID %s" % (assertion,),
            "X-Client-State": "616161",
        }
        mock_response = {
            "status": "okay",
            "email": "testuser@example.com",
            "idpClaims": {"fxa-generation": 13, 'fxa-keysChangedAt': 12},
        }
        with self.mock_browserid_verifier(response=mock_response):
            res = self.app.get("/1.0/sync/1.1", headers=headers_browserid)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["uid"], res.json["uid"])
        self.assertEqual(token["fxa_uid"], "testuser")
        self.assertEqual(token["fxa_kid"], "0000000000012-YWFh")
        self.assertNotEqual(token["hashed_fxa_uid"], token["fxa_uid"])
        self.assertEqual(token["hashed_fxa_uid"], res.json["hashed_fxa_uid"])
        self.assertIn("hashed_device_id", token)

    def test_uid_and_kid_from_oauth_token(self):
        oauth_token = self._gettoken(email="testuser@example.com")
        headers_oauth = {
            "Authorization": "Bearer %s" % (oauth_token,),
            "X-KeyID": "12-YWFh",
        }
        res = self.app.get("/1.0/sync/1.1", headers=headers_oauth)
        token = self.unsafelyParseToken(res.json["id"])
        self.assertEqual(token["uid"], res.json["uid"])
        self.assertEqual(token["fxa_uid"], "testuser")
        self.assertEqual(token["fxa_kid"], "0000000000012-YWFh")
        self.assertNotEqual(token["hashed_fxa_uid"], token["fxa_uid"])
        self.assertEqual(token["hashed_fxa_uid"], res.json["hashed_fxa_uid"])
        self.assertIn("hashed_device_id", token)

    def test_metrics_uid_is_returned_in_response(self):
        assert "fxa.metrics_uid_secret_key" in self.config.registry.settings
        assertion = self._getassertion(email="newuser2@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        self.assertTrue('hashed_fxa_uid' in res.json)

    def test_node_type_is_returned_in_response(self):
        assertion = self._getassertion(email="newuser2@test.com")
        headers = {'Authorization': 'BrowserID %s' % assertion}
        res = self.app.get('/1.0/sync/1.1', headers=headers, status=200)
        self.assertEqual(res.json['node_type'], 'example')


class TestServiceWithSQLBackend(TestService):

    spanner_node = "https://spanner.example.com"
    mysql_node = "https://example.com"

    def get_ini(self):
        return os.path.join(os.path.dirname(__file__),
                            'test_sql.ini')

    def setUp(self):
        super(TestServiceWithSQLBackend, self).setUp()
        # Start each test with a blank slate.
        self.backend._safe_execute('delete from services')
        self.backend._safe_execute('delete from nodes')
        self.backend._safe_execute('delete from users')
        # Ensure the necessary service exists in the db.
        self.backend.add_service('sync-1.1', '{node}/1.1/{uid}')
        self.backend.add_service('sync-1.5', '{node}/1.5/{uid}')
        # Ensure we have a node with enough capacity to run the tests.
        self.backend.add_node('sync-1.1', self.mysql_node, 100)
        self.backend.add_node('sync-1.5', self.mysql_node, 100)
        # Ensure we have a spanner node, but give it no capacity
        # so users are not assigned to it except under special
        # circumstances.
        self.backend.add_node('sync-1.5', self.spanner_node, 0, nodeid=800)

    def tearDown(self):
        # And clean up at the end, for good measure.
        self.backend._safe_execute('delete from services')
        self.backend._safe_execute('delete from nodes')
        self.backend._safe_execute('delete from users')
        super(TestServiceWithSQLBackend, self).tearDown()

    def test_assign_new_users_to_spanner(self):
        self.backend.migrate_new_user_percentage = 1
        # These emails are carefully selected so that the first is assigned
        # to spanner, but the second will not be.
        EMAIL0 = "abO-test@example.com"
        EMAIL1 = "abT-test@example.com"
        user0 = self.backend.allocate_user("sync-1.5", EMAIL0)
        user1 = self.backend.allocate_user("sync-1.5", EMAIL1)
        self.assertEquals(user0['node'], self.spanner_node)
        self.assertEquals(user1['node'], self.mysql_node)


class TestServiceWithNoBackends(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_settings({ # noqa; identation below is non-standard
            "tokenserver.backend":
              "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend", # noqa
            "tokenserver.secrets.backend":
              "mozsvc.secrets.FixedSecrets",
            "tokenserver.secrets.secrets":
              "ssshh-its-a-secret",
            "tokenserver.applications":
              "sync-1.1",
        })
        self.config.include("tokenserver")
        self.config.commit()
        wsgiapp = self.config.make_wsgi_app()
        self.app = TestApp(wsgiapp)

    def test_discovery(self):
        res = self.app.get('/')
        self.assertEqual(res.json, {
            'auth': 'http://localhost',
            'services': {
                'sync': ['1.1'],
            },
        })

    def test_browserid_is_unsupported(self):
        res = self.app.get('/1.0/sync/1.1', headers={
            'Authorization': 'BrowserID xxxxxxxx'
        }, status=401)
        self.assertEqual(res.json['status'], 'error')
        self.assertEqual(res.json['errors'][0]['description'], 'Unsupported')

    def test_oauth_is_unsupported(self):
        res = self.app.get('/1.0/sync/1.1', headers={
            'Authorization': 'Bearer xxxxxxxx'
        }, status=401)
        self.assertEqual(res.json['status'], 'error')
        self.assertEqual(res.json['errors'][0]['description'], 'Unsupported')


class TestServiceWithNoBrowserID(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_settings({ # noqa; identation below is non-standard
            "tokenserver.backend":
              "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend", # noqa
            "tokenserver.secrets.backend":
              "mozsvc.secrets.FixedSecrets",
            "tokenserver.secrets.secrets":
              "ssshh-its-a-secret",
            "tokenserver.applications":
              "sync-1.1",
            "oauth.backend":
              "tokenserver.verifiers.RemoteOAuthVerifier",
        })
        self.config.include("tokenserver")
        self.config.commit()
        wsgiapp = self.config.make_wsgi_app()
        self.app = TestApp(wsgiapp)

    def test_discovery(self):
        res = self.app.get('/')
        self.assertEqual(res.json, {
            'auth': 'http://localhost',
            'services': {
                'sync': ['1.1'],
            },
            'oauth': {
                'default_issuer': 'api.accounts.firefox.com',
                'scope': 'https://identity.mozilla.com/apps/oldsync',
                'server_url': 'https://oauth.accounts.firefox.com/v1',
            },
        })

    def test_browserid_is_unsupported(self):
        res = self.app.get('/1.0/sync/1.1', headers={
            'Authorization': 'BrowserID xxxxxxxx'
        }, status=401)
        self.assertEqual(res.json['status'], 'error')
        self.assertEqual(res.json['errors'][0]['description'], 'Unsupported')

    def test_oauth_is_supported(self):
        res = self.app.get('/1.0/sync/1.1', headers={
            'Authorization': 'Bearer xxxxxxxx'
        }, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')


class TestServiceWithNoOAuth(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_settings({ # noqa; identation below is non-standard
            "tokenserver.backend":
              "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend", # noqa
            "tokenserver.secrets.backend":
              "mozsvc.secrets.FixedSecrets",
            "tokenserver.secrets.secrets":
              "ssshh-its-a-secret",
            "tokenserver.applications":
              "sync-1.1",
            "browserid.backend":
              "tokenserver.verifiers.LocalBrowserIdVerifier",
        })
        self.config.include("tokenserver")
        self.config.commit()
        wsgiapp = self.config.make_wsgi_app()
        self.app = TestApp(wsgiapp)

    def test_discovery(self):
        res = self.app.get('/')
        self.assertEqual(res.json, {
            'auth': 'http://localhost',
            'services': {
                'sync': ['1.1'],
            },
            'browserid': {
                'allowed_issuers': None,
                'trusted_issuers': None,
            },
        })

    def test_browserid_is_supported(self):
        assertion = make_assertion('x', 'y').encode('ascii')
        res = self.app.get('/1.0/sync/1.1', headers={
            'Authorization': 'BrowserID ' + assertion
        }, status=401)
        self.assertEqual(res.json['status'], 'invalid-credentials')

    def test_oauth_is_unsupported(self):
        res = self.app.get('/1.0/sync/1.1', headers={
            'Authorization': 'Bearer xxxxxxxx'
        }, status=401)
        self.assertEqual(res.json['status'], 'error')
        self.assertEqual(res.json['errors'][0]['description'], 'Unsupported')
