# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import unittest

from pyramid import testing

from tokenserver.assignment import INodeAssignment
from mozsvc.config import load_into_settings

DEFAULT_EMAIL = "alexis@mozilla.com"
DEFAULT_NODE = "https://example.com"
DEFAULT_SERVICE = "sync-1.0"


class TestFixedBackend(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.ini = os.path.join(os.path.dirname(__file__),
                                'test_memorynode.ini')
        settings = {}
        load_into_settings(self.ini, settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")
        self.backend = self.config.registry.getUtility(INodeAssignment)
        self.backend.clear()

    def tearDown(self):
        self.backend.clear()

    def test_read_config(self):
        user = self.backend.allocate_user(DEFAULT_SERVICE, DEFAULT_EMAIL)
        self.assertEqual(user['node'], DEFAULT_NODE)

    def test_assignation(self):
        user = self.backend.get_user(DEFAULT_SERVICE, DEFAULT_EMAIL)
        self.assertEquals(user, None)

        user = self.backend.allocate_user(DEFAULT_EMAIL, DEFAULT_SERVICE)
        self.assertEquals(user['uid'], 1)
        self.assertEquals(user['node'], DEFAULT_NODE)

        user = self.backend.get_user(DEFAULT_EMAIL, DEFAULT_SERVICE)
        self.assertEquals(user['uid'], 1)
        self.assertEquals(user['node'], DEFAULT_NODE)
