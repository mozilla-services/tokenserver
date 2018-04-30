# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import socket
import unittest
import responses
import contextlib

from pyramid.config import Configurator

from tokenserver.verifiers import (
    IOAuthVerifier,
    ConnectionError,
    RemoteOAuthVerifier,
)

import fxa.errors


MOCK_TOKEN = 'token'


class TestRemoteOAuthVerifier(unittest.TestCase):

    DEFAULT_SETTINGS = {  # noqa; identation below is non-standard
        "tokenserver.backend":
            "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend",
        "oauth.backend":
            "tokenserver.verifiers.RemoteOAuthVerifier",
        "tokenserver.secrets.backend":
            "mozsvc.secrets.FixedSecrets",
        "tokenserver.secrets.secrets":
            "steve-let-the-dogs-out",
    }

    def _make_config(self, settings={}):
        all_settings = self.DEFAULT_SETTINGS.copy()
        all_settings.update(settings)
        config = Configurator(settings=all_settings)
        config.include("tokenserver")
        config.commit()
        return config

    @contextlib.contextmanager
    def _mock_verifier(self, verifier, response=None, exc=None):
        def replacement_verify_token_method(*args, **kwds):
            if exc is not None:
                raise exc
            if response is not None:
                return response
            raise RuntimeError("incomplete mock")
        orig_verify_token_method = verifier._client.verify_token
        verifier._client.verify_token = replacement_verify_token_method
        try:
            yield None
        finally:
            verifier._client.verify_token = orig_verify_token_method

    def test_verifier_config_loading_defaults(self):
        config = self._make_config()
        verifier = config.registry.getUtility(IOAuthVerifier)
        self.assertTrue(isinstance(verifier, RemoteOAuthVerifier))
        self.assertEquals(verifier.server_url,
                          "https://oauth.accounts.firefox.com/v1")
        self.assertEquals(verifier.default_issuer,
                          "api.accounts.firefox.com")
        self.assertEquals(verifier.scope,
                          "https://identity.mozilla.com/apps/oldsync")
        self.assertEquals(verifier.timeout, 30)

    def test_verifier_config_loading_values(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "oauth.server_url":
                "https://oauth-test1.dev.lcip.org/",
            "oauth.default_issuer":
                "myissuer.com",
            "oauth.scope":
                "some.custom.scope",
            "oauth.timeout": 500
        })
        verifier = config.registry.getUtility(IOAuthVerifier)
        self.assertTrue(isinstance(verifier, RemoteOAuthVerifier))
        self.assertEquals(verifier.server_url,
                          "https://oauth-test1.dev.lcip.org/v1")
        self.assertEquals(verifier.default_issuer, "myissuer.com")
        self.assertEquals(verifier.scope, "some.custom.scope")
        self.assertEquals(verifier.timeout, 500)

    @responses.activate
    def test_verifier_config_dynamic_issuer_discovery(self):
        responses.add(
            responses.GET,
            "https://oauth-server.my-self-hosted-setup.com/config",
            json={
                "browserid": {
                    "issuer": "authy.my-self-hosted-setup.com",
                },
            }
        )
        config = self._make_config({  # noqa; indentation below is non-standard
            "oauth.server_url":
                "https://oauth-server.my-self-hosted-setup.com/",
        })
        verifier = config.registry.getUtility(IOAuthVerifier)
        self.assertEqual(len(responses.calls), 1)
        self.assertTrue(isinstance(verifier, RemoteOAuthVerifier))
        self.assertEquals(verifier.server_url,
                          "https://oauth-server.my-self-hosted-setup.com/v1")
        self.assertEquals(verifier.default_issuer,
                          "authy.my-self-hosted-setup.com")

    @responses.activate
    def test_verifier_config_handles_missing_default_issuer(self):
        responses.add(
            responses.GET,
            "https://oauth-server.my-self-hosted-setup.com/config",
            json={
                "browserid": {
                    "oh no": "the issuer is not configured here"
                },
            }
        )
        config = self._make_config({  # noqa; indentation below is non-standard
            "oauth.server_url":
                "https://oauth-server.my-self-hosted-setup.com/",
        })
        verifier = config.registry.getUtility(IOAuthVerifier)
        self.assertEqual(len(responses.calls), 1)
        self.assertTrue(isinstance(verifier, RemoteOAuthVerifier))
        self.assertEquals(verifier.server_url,
                          "https://oauth-server.my-self-hosted-setup.com/v1")
        self.assertEquals(verifier.default_issuer, None)

    def test_verifier_config_rejects_empty_scope(self):
        with self.assertRaises(ValueError):
            self._make_config({
                "oauth.scope": ""
            })

    def test_verifier_failure_cases(self):
        config = self._make_config()
        verifier = config.registry.getUtility(IOAuthVerifier)
        with self._mock_verifier(verifier, exc=socket.error):
            with self.assertRaises(ConnectionError):
                verifier.verify(MOCK_TOKEN)
        err = fxa.errors.ScopeMismatchError(verifier.scope, 'wrong.scope')
        with self._mock_verifier(verifier, exc=err):
            with self.assertRaises(fxa.errors.ScopeMismatchError):
                verifier.verify(MOCK_TOKEN)

    def test_verifier_constructs_email_from_uid_and_reported_issuer(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "oauth.default_issuer":
                "my.default.issuer.com",
        })
        verifier = config.registry.getUtility(IOAuthVerifier)
        mock_response = {"user": "UID", "issuer": "my.custom.issuer.com"}
        with self._mock_verifier(verifier, response=mock_response):
            self.assertEquals(verifier.verify(MOCK_TOKEN)["email"],
                              "UID@my.custom.issuer.com")

    def test_verifier_constructs_email_from_uid_and_default_issuer(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "oauth.default_issuer":
                "my.custom.issuer.com",
        })
        verifier = config.registry.getUtility(IOAuthVerifier)
        with self._mock_verifier(verifier, response={"user": "UID"}):
            self.assertEquals(verifier.verify(MOCK_TOKEN)["email"],
                              "UID@my.custom.issuer.com")

    @responses.activate
    def test_verifier_fails_if_issuer_cannot_be_determined(self):
        responses.add(
            responses.GET,
            "https://oauth-server.my-self-hosted-setup.com/config",
            json={},
        )
        config = self._make_config({  # noqa; indentation below is non-standard
            "oauth.server_url":
                "https://oauth-server.my-self-hosted-setup.com/",
        })
        verifier = config.registry.getUtility(IOAuthVerifier)
        self.assertEqual(len(responses.calls), 1)
        with self._mock_verifier(verifier, response={"user": "UID"}):
            with self.assertRaises(fxa.errors.TrustError):
                verifier.verify(MOCK_TOKEN)
