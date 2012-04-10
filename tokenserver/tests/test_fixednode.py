# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
from collections import defaultdict

from pyramid import testing

from tokenserver.assignment import INodeAssignment
from tokenserver.assignment import fixednode
from mozsvc.config import load_into_settings
from mozsvc.exceptions import BackendError
from tokenserver.tests.support import unittest

DEFAULT_EMAIL = "alexis@mozilla.com"
DEFAULT_NODE = "https://example.com"
DEFAULT_SERVICE = "sync-1.0"


def restore_defaults():
    fixednode._UID = 0
    fixednode._USERS_UIDS = defaultdict(dict)


class TestFixedBackend(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.ini = os.path.join(os.path.dirname(__file__),
                                'test_fixednode.ini')
        settings = {}
        load_into_settings(self.ini, settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")
        self.backend = self.config.registry.getUtility(INodeAssignment)

    def test_read_config(self):
        self.assertEqual(DEFAULT_NODE,
                self.backend.allocate_node(DEFAULT_EMAIL, DEFAULT_SERVICE,
                    )[1])

    def test_assignation(self):
        # restore the default values for testing
        restore_defaults()
        try:
            # getting the node assignation for an existing user should return
            # None and the service entry
            self.assertEquals(
                    self.backend.get_node(DEFAULT_EMAIL, DEFAULT_SERVICE,
                        ),
                    (None, DEFAULT_NODE))

            # Now allocate an user to a node
            self.assertEquals(
                    self.backend.allocate_node(DEFAULT_EMAIL, DEFAULT_SERVICE,
                        ),
                    (0, DEFAULT_NODE))

            # Trying to allocate it two times should raise a Backend error
            self.assertRaises(BackendError, self.backend.allocate_node,
                              DEFAULT_EMAIL, DEFAULT_SERVICE)

            # getting the value of it later should also work properly
            self.assertEquals(
                    self.backend.get_node(DEFAULT_EMAIL, DEFAULT_SERVICE,
                        ),
                    (0, DEFAULT_NODE))
        finally:
            restore_defaults()
