# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import unittest
from pyramid import testing
import time

from webtest import TestApp
from logging.config import fileConfig
from ConfigParser import NoSectionError

from mozsvc.util import CatchErrors
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver.assignment import INodeAssignment
from tokenserver.crypto.master import stop_runners

from tokenserver.verifiers import PowerHoseVerifier
from tokenserver.crypto.pyworker import CryptoWorker
from tokenserver.tests.support import (
    PurePythonRunner,
    CERTS_LOCATION,
    get_assertion
)

from vep.errors import InvalidSignatureError

TOKEN_URI = '/1.0/sync/2.1'


class TestPowerHoseVerifier(unittest.TestCase):

    def test_assertion_verification(self):
        # giving a valid assertion should return True
        worker = CryptoWorker(CERTS_LOCATION)
        verifier = PowerHoseVerifier(runner=PurePythonRunner(worker))
        self.assertTrue(verifier.verify(get_assertion("alexis@mozilla.com")))

        # giving a wrong assertion (invalid bundled certificate) raise an
        # exception

        self.assertRaises(InvalidSignatureError, verifier.verify,
                get_assertion("alexis@mozilla.com", bad_issuer_cert=True))

        self.assertRaises(InvalidSignatureError, verifier.verify,
                get_assertion("alexis@mozilla.com", bad_email_cert=True))

        self.assertRaises(InvalidSignatureError, verifier.verify,
                get_assertion("alexis@mozilla.com", bad_email_cert=True,
                              bad_issuer_cert=True))


class TestPowerService(unittest.TestCase):

    @classmethod
    def get_ini(self):
        return os.path.join(os.path.dirname(__file__), 'test_powerhose.ini')

    @classmethod
    def setUpClass(cls):
        cls.config = testing.setUp()
        settings = {}
        try:
            fileConfig(cls.get_ini())
        except NoSectionError:
            pass
        load_into_settings(cls.get_ini(), settings)
        cls.config.add_settings(settings)
        cls.config.include("tokenserver")
        load_and_register("tokenserver", cls.config)
        cls.backend = cls.config.registry.getUtility(INodeAssignment)

    @classmethod
    def tearDownClass(cls):
        stop_runners()

    def setUp(self):
        wsgiapp = TestPowerService.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)
        time.sleep(1.)

    def test_valid_app(self):
        assertion = get_assertion("alexis@mozilla.com")
        headers = {'Authorization': 'Browser-ID %s' % assertion}
        res = self.app.get(TOKEN_URI, headers=headers)
        self.assertEqual(res.json['service_entry'], 'http://example.com')

    def test_authentication_failures(self):
        # sending a request without any authentication header should result in
        # a 401 Unauthorized response.
        self.app.get(TOKEN_URI, status=401)

        # sending a request with a broken authentication header should return a
        # 401 as well
        headers = {'Authorization': 'VELOCIRAPTOR'}
        self.app.get(TOKEN_URI, headers=headers, status=401)

        # the authentication should be browserid
        headers = {'Authorization': 'Basic-Auth alexis:alexis'}
        res = self.app.get(TOKEN_URI, headers=headers, status=401)
        self.assertTrue('WWW-Authenticate' in res.headers)
        self.assertEqual(res.headers['WWW-Authenticate'], 'Browser-ID ')

        # if the headers are good but the given assertion is not valid, a 401
        # should be raised as well.
        wrong_assertion = get_assertion("alexis@mozilla.com",
                                        bad_issuer_cert=True)
        headers = {'Authorization': 'Browser-ID %s' % wrong_assertion}
        res = self.app.get(TOKEN_URI, headers=headers, status=401)
