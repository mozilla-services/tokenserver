# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import re
import threading
from wsgiref.simple_server import make_server

import tokenlib
import hawkauthlib
import pyramid.testing

from mozsvc.config import load_into_settings

from tokenserver.assignment import INodeAssignment
from tokenserver.tests.support import unittest
from tokenserver.scripts.purge_old_records import purge_old_records


class TestPurgeOldRecordsScript(unittest.TestCase):
    """A testcase for proper functioning of the purge_old_records.py script.

    This is a tricky one, because we have to actually run the script and
    test that it does the right thing.  We also run a mock downstream service
    so we can test that data-deletion requests go through ok.
    """

    def setUp(self):
        super(TestPurgeOldRecordsScript, self).setUp()

        # Run a testing service in a separate thread
        # so that we can test for proper calls being made.
        self.service_requests = []
        self.service_node = "http://localhost:8002"
        self.service = make_server("localhost", 8002, self._service_app)
        target = self.service.serve_forever
        self.service_thread = threading.Thread(target=target)
        self.service_thread.start()
        # This silences nuisance on-by-default logging output.
        self.service.RequestHandlerClass.log_request = lambda *a: None

        # Make a stub tokenserver app in-line.
        self.config = pyramid.testing.setUp()
        self.ini_file = os.path.join(os.path.dirname(__file__), 'test_sql.ini')
        settings = {}
        load_into_settings(self.ini_file, settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")

        # Configure the node-assignment backend to talk to our test service.
        self.backend = self.config.registry.getUtility(INodeAssignment)
        self.backend.add_service("test-1.0", "{node}/1.0/{uid}")
        self.backend.add_node("test-1.0", self.service_node, 100)

    def tearDown(self):
        if self.backend._engine.driver == 'pysqlite':
            filename = self.backend.sqluri.split('sqlite://')[-1]
            if os.path.exists(filename):
                os.remove(filename)
        else:
            self.backend._safe_execute('delete from services')
            self.backend._safe_execute('delete from nodes')
            self.backend._safe_execute('delete from users')
        pyramid.testing.tearDown()
        self.service.shutdown()
        self.service_thread.join()

    def _service_app(self, environ, start_response):
        self.service_requests.append(environ)
        start_response("200 OK", [])
        return ""

    def test_purging_of_old_user_records(self):
        # Make some old user records.
        service = "test-1.0"
        email = "test@mozilla.com"
        user = self.backend.create_user(service, email, client_state="a")
        self.backend.update_user(service, user, client_state="b")
        self.backend.update_user(service, user, client_state="c")
        user_records = list(self.backend.get_user_records(service, email))
        self.assertEqual(len(user_records), 3)
        user = self.backend.get_user(service, email)
        self.assertEquals(user["client_state"], "c")
        self.assertEquals(len(user["old_client_states"]), 2)

        # The default grace-period should prevent any cleanup.
        self.assertTrue(purge_old_records(self.ini_file))
        user_records = list(self.backend.get_user_records(service, email))
        self.assertEqual(len(user_records), 3)
        self.assertEqual(len(self.service_requests), 0)

        # With no grace period, we should cleanup two old records.
        self.assertTrue(purge_old_records(self.ini_file, grace_period=0))
        user_records = list(self.backend.get_user_records(service, email))
        self.assertEqual(len(user_records), 1)
        self.assertEqual(len(self.service_requests), 2)

        # Check that the proper delete requests were made to the service.
        secrets = self.config.registry.settings["tokenserver.secrets"]
        node_secret = secrets.get(self.service_node)[-1]
        for environ in self.service_requests:
            # They must be to the correct path.
            self.assertEquals(environ["REQUEST_METHOD"], "DELETE")
            self.assertTrue(re.match("/1.0/[0-9]+", environ["PATH_INFO"]))
            # They must have a correct request signature.
            token = hawkauthlib.get_id(environ)
            secret = tokenlib.get_derived_secret(token, secret=node_secret)
            self.assertTrue(hawkauthlib.check_signature(environ, secret))

        # Check that the user's current state is unaffected
        user = self.backend.get_user(service, email)
        self.assertEquals(user["client_state"], "c")
        self.assertEquals(len(user["old_client_states"]), 0)
