# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import unittest
from pyramid import testing
import time

from vep.verifiers.local import LocalVerifier
import threading
from tokenserver.bid import IPowerhoseRunner, get_worker, stop_runners
from mozsvc.config import load_into_settings
from tokenserver.tests.test_service import TestService
from webtest import TestApp
import unittest
import json
import os
from pyramid import testing

from tokenserver import main
from vep import DummyVerifier
from mozsvc.util import CatchErrors
from mozsvc.config import load_into_settings
from tokenserver.backend import INodeAssignment
from mozsvc.plugin import load_and_register



class Worker(threading.Thread):
    def __init__(self, endpoint):
        threading.Thread.__init__(self)
        self.endpoint = endpoint

    def run(self):
        self.worker = get_worker(self.endpoint)
        try:
            self.worker.run()
        except Exception:
            self.worker.stop()

    def join(self):
        self.worker.stop()
        threading.Thread.join(self)


class TestPowerService(unittest.TestCase):
    def get_ini(self):
        return os.path.join(os.path.dirname(__file__),
                            'test_powerhose.ini')

    def _getassertion(self):
        email = 'tarek@mozilla.com'
        url = 'http://tokenserver.services.mozilla.com'
        return self.verifier.make_assertion(email, url)

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
        self.verifier = DummyVerifier
        self.worker = Worker("ipc:///tmp/master-routing.ipc")
        self.worker.start()
        time.sleep(.1)

    def tearDown(self):
        self.worker.join()
        stop_runners()

    def test_valid_app(self):
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        res = self.app.get('/1.0/sync/2.1', headers=headers)
        self.assertEqual(res.json['service_entry'], 'http://example.com')
