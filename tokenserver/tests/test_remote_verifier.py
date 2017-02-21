# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import contextlib
import unittest

from pyramid.config import Configurator

from tokenserver.verifiers import RemoteVerifier, IBrowserIdVerifier
from browserid.tests.support import make_assertion
import browserid.errors


class mockobj(object):
    pass


class TestRemoteVerifier(unittest.TestCase):

    DEFAULT_SETTINGS = {  # noqa; identation below is non-standard
        "tokenserver.backend":
            "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend",
        "browserid.backend":
            "tokenserver.verifiers.RemoteVerifier",
        "tokenserver.secrets.backend":
            "mozsvc.secrets.FixedSecrets",
        "tokenserver.secrets.secrets":
            "steve-let-the-dogs-out",
        "browserid.backend":
            "tokenserver.verifiers.RemoteVerifier",
    }

    def _make_config(self, settings={}):
        all_settings = self.DEFAULT_SETTINGS.copy()
        all_settings.update(settings)
        config = Configurator(settings=all_settings)
        config.include("tokenserver")
        config.commit()
        return config

    @contextlib.contextmanager
    def _mock_verifier(self, verifier, exc=None, **response_attrs):
        def replacement_post_method(*args, **kwds):
            if exc is not None:
                raise exc
            response = mockobj()
            response.status_code = 200
            response.text = ""
            response.__dict__.update(response_attrs)
            return response
        orig_post_method = verifier.session.post
        verifier.session.post = replacement_post_method
        try:
            yield None
        finally:
            verifier.session.post = orig_post_method

    def test_verifier_config_loading_defaults(self):
        config = self._make_config()
        verifier = config.registry.getUtility(IBrowserIdVerifier)
        self.assertTrue(isinstance(verifier, RemoteVerifier))
        self.assertEquals(verifier.verifier_url,
                          "https://verifier.accounts.firefox.com/v2")
        self.assertEquals(verifier.audiences, None)
        self.assertEquals(verifier.trusted_issuers, None)
        self.assertEquals(verifier.allowed_issuers, None)

    def test_verifier_config_loading_values(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "browserid.verifier_url":
                "https://trustyverifier.notascam.com/endpoint/path",
            "browserid.audiences":
                "https://testmytoken.com",
            "browserid.trusted_issuers":
                "example.com trustyidp.org",
            "browserid.allowed_issuers":
                "example.com trustyidp.org\nmockmyid.com",
        })
        verifier = config.registry.getUtility(IBrowserIdVerifier)
        self.assertTrue(isinstance(verifier, RemoteVerifier))
        self.assertEquals(verifier.verifier_url,
                          "https://trustyverifier.notascam.com/endpoint/path")
        self.assertEquals(verifier.audiences, "https://testmytoken.com")
        self.assertEquals(verifier.trusted_issuers,
                          ["example.com", "trustyidp.org"])
        self.assertEquals(verifier.allowed_issuers,
                          ["example.com", "trustyidp.org", "mockmyid.com"])

    def test_verifier_failure_cases(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "browserid.audiences":
                "https://testmytoken.com",
        })
        verifier = config.registry.getUtility(IBrowserIdVerifier)
        assertion = make_assertion(email="test@example.com",
                                   audience="https://testmytoken.com")
        with self._mock_verifier(verifier, status_code=500):
            with self.assertRaises(browserid.errors.ConnectionError):
                verifier.verify(assertion)
        with self._mock_verifier(verifier, text="<h1>Server Error</h1>"):
            with self.assertRaises(browserid.errors.ConnectionError):
                verifier.verify(assertion)
        with self._mock_verifier(verifier, text='{"status": "error"}'):
            with self.assertRaises(browserid.errors.InvalidSignatureError):
                verifier.verify(assertion)
        with self._mock_verifier(verifier, text='{"status": "potato"}'):
            with self.assertRaises(browserid.errors.InvalidSignatureError):
                verifier.verify(assertion)

    def test_verifier_rejects_unallowed_issuers(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "browserid.audiences":
                "https://testmytoken.com",
            "browserid.allowed_issuers":
                "accounts.firefox.com mockmyid.com",
        })
        verifier = config.registry.getUtility(IBrowserIdVerifier)
        assertion = make_assertion(email="test@example.com",
                                   audience="https://testmytoken.com")
        mock_response = {
            "status": "okay",
            "principal": {
                "email": "test@example.com",
            },
            "audience": "https://testmytoken.com",
            "issuer": "login.persona.org",
        }
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
        mock_response["issuer"] = "mockmyid.com"
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            self.assertEquals(verifier.verify(assertion)["principal"]["email"],
                              "test@example.com")
        mock_response["issuer"] = "accounts.firefox.com"
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            self.assertEquals(verifier.verify(assertion)["principal"]["email"],
                              "test@example.com")
        mock_response["issuer"] = "mockmyid.org"
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
        mock_response["issuer"] = "http://mockmyid.com"
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
        mock_response["issuer"] = "mockmyid.co"
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
        mock_response["issuer"] = 42
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
        mock_response["issuer"] = None
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
        del mock_response["issuer"]
        with self._mock_verifier(verifier, text=json.dumps(mock_response)):
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
