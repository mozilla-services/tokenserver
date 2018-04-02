# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest

from pyramid.config import Configurator

from tokenserver.verifiers import LocalBrowserIdVerifier, IBrowserIdVerifier
from browserid.tests.support import (make_assertion,
                                     patched_supportdoc_fetching)
import browserid.errors


class mockobj(object):
    pass


class TestLocalBrowserIdVerifier(unittest.TestCase):

    DEFAULT_SETTINGS = {  # noqa; identation below is non-standard
        "tokenserver.backend":
            "tokenserver.assignment.memorynode.MemoryNodeAssignmentBackend",
        "browserid.backend":
            "tokenserver.verifiers.LocalBrowserIdVerifier",
        "tokenserver.secrets.backend":
            "mozsvc.secrets.FixedSecrets",
        "tokenserver.secrets.secrets":
            "bruce-let-the-dogs-out",
    }

    def _make_config(self, settings={}):
        all_settings = self.DEFAULT_SETTINGS.copy()
        all_settings.update(settings)
        config = Configurator(settings=all_settings)
        config.include("tokenserver")
        config.commit()
        return config

    def test_verifier_config_loading_defaults(self):
        config = self._make_config()
        verifier = config.registry.getUtility(IBrowserIdVerifier)
        self.assertTrue(isinstance(verifier, LocalBrowserIdVerifier))
        self.assertEquals(verifier.audiences, None)
        self.assertEquals(verifier.trusted_issuers, None)
        self.assertEquals(verifier.allowed_issuers, None)

    def test_verifier_config_loading_values(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "browserid.audiences":
                "https://testmytoken.com",
            "browserid.trusted_issuers":
                "example.com trustyidp.org",
            "browserid.allowed_issuers":
                "example.com trustyidp.org\nmockmyid.com",
        })
        verifier = config.registry.getUtility(IBrowserIdVerifier)
        self.assertTrue(isinstance(verifier, LocalBrowserIdVerifier))
        self.assertEquals(verifier.audiences, "https://testmytoken.com")
        self.assertEquals(verifier.trusted_issuers,
                          ["example.com", "trustyidp.org"])
        self.assertEquals(verifier.allowed_issuers,
                          ["example.com", "trustyidp.org", "mockmyid.com"])

    def test_verifier_rejects_unallowed_issuers(self):
        config = self._make_config({  # noqa; indentation below is non-standard
            "browserid.audiences":
                "https://testmytoken.com",
            "browserid.trusted_issuers":
                "accounts.firefox.com trustyidp.org",
            "browserid.allowed_issuers":
                "accounts.firefox.com mockmyid.com",
        })
        with patched_supportdoc_fetching():
            verifier = config.registry.getUtility(IBrowserIdVerifier)
            # The issuer is both trusted, and allowed.
            assertion = make_assertion(email="test@example.com",
                                       audience="https://testmytoken.com",
                                       issuer="accounts.firefox.com")
            self.assertEquals(verifier.verify(assertion)["email"],
                              "test@example.com")
            # The issuer is allowed and is the primary.
            assertion = make_assertion(email="test@mockmyid.com",
                                       audience="https://testmytoken.com",
                                       issuer="mockmyid.com")
            self.assertEquals(verifier.verify(assertion)["email"],
                              "test@mockmyid.com")
            # The issuer is allowed, but not trusted as a secondary.
            assertion = make_assertion(email="test@example.com",
                                       audience="https://testmytoken.com",
                                       issuer="mockmyid.com")
            with self.assertRaises(browserid.errors.InvalidSignatureError):
                verifier.verify(assertion)
            # The issuer is trsuted, but is not allowed.
            assertion = make_assertion(email="test@example.com",
                                       audience="https://testmytoken.com",
                                       issuer="trustyidp.org")
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
            # The issuer is the primary, but is not allowed.
            assertion = make_assertion(email="test@example.com",
                                       audience="https://testmytoken.com",
                                       issuer="example.com")
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
            # Various tests for string pattern-matching edgecases.
            # All of these are primaries, but not allowed.
            assertion = make_assertion(email="test@mockmyid.org",
                                       audience="https://testmytoken.com",
                                       issuer="mockmyid.org")
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
            assertion = make_assertion(email="test@mockmyid.co",
                                       audience="https://testmytoken.com",
                                       issuer="mockmyid.co")
            with self.assertRaises(browserid.errors.InvalidIssuerError):
                verifier.verify(assertion)
