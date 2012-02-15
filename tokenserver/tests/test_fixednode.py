# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import unittest
from pyramid import testing

from tokenserver.backend import INodeAssignment
from mozsvc.config import load_into_settings


class TestFixedBackend(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.ini = os.path.join(os.path.dirname(__file__), 'test_fixednode.ini')
        settings = {}
        load_into_settings(self.ini, settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")
        self.backend = self.config.registry.getUtility(INodeAssignment)

    def test_read_config(self):
        wanted = 'http://example.com'
        self.assertEqual(wanted, self.backend.create_node(None, None))
        self.assertEqual(wanted, self.backend.get_node(None, None))

    def _test_ldap_node_assignment_backend(self):
        ldap = "ldap://user:password@server"
        sreg = "http://to.sreg.server"
        snode = "http://to.snode.server"
        backend = LDAPNodeAssignmentBackend(ldap, sreg, snode, None)

        # in case we esplicitely ask for an unknown user, we return None
        backend.get_node(email, service)

        # in this case, adding an user makes a call to sreg
        node = backend.create_node(email, service)
