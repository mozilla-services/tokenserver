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

from vep.tests.support import make_assertion

from mozsvc.util import CatchErrors
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver.assignment import INodeAssignment
from tokenserver.crypto.master import stop_runners
from tokenserver import logger

from tokenserver.verifiers import PowerHoseVerifier
from tokenserver.crypto.pyworker import CryptoWorker
from tokenserver.tests.support import (
    load_key,
    PurePythonRunner,
    CERTS_LOCATION
)


def _get_assertion():
    email = "alexis@mozilla.com"
    audience = "*"
    key = load_key("browserid.org")
    pub = key.rsa.pub()[1].decode('latin-1')
    return make_assertion(email, audience,
                          issuer_keypair=(pub, key),
                          email_keypair=(pub, key))


class TestPowerHoseVerifier(unittest.TestCase):

    def test_assertion_verification(self):
        # giving a valid assertion should return True
        worker = CryptoWorker(CERTS_LOCATION)
        verifier = PowerHoseVerifier(runner=PurePythonRunner(worker))
        verifier.verify(_get_assertion())


class TestPowerService(unittest.TestCase):
    def get_ini(self):
        return os.path.join(os.path.dirname(__file__),
                            'test_powerhose.ini')

    def setUp(self):
        logger.debug("TestPowerService.setUp")
        self.config = testing.setUp()
        settings = {}
        try:
            fileConfig(self.get_ini())
        except NoSectionError:
            pass
        load_into_settings(self.get_ini(), settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")
        load_and_register("tokenserver", self.config)
        self.backend = self.config.registry.getUtility(INodeAssignment)
        wsgiapp = self.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)
        time.sleep(1.)

    def tearDown(self):
        logger.debug("TestPowerService.tearDown")
        stop_runners()
        logger.debug("TestPowerService.tearDown over")

    def test_valid_app(self):
        logger.debug("TestPowerService.test_valid_app")
        headers = {'Authorization': 'Browser-ID %s' % _get_assertion()}
        res = self.app.get('/1.0/sync/2.1', headers=headers)
        self.assertEqual(res.json['service_entry'], 'http://example.com')
