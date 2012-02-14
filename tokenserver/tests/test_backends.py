# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from tokenserver.backends import (
    DefaultNodeAssignmentBackend,
    LDAPNodeAssignmentBackend
)

from tokenserver import backends


class TestBackends(unittest.TestCase):

    def test_default_node_assigment_backend(self):
        backend = DefaultNodeAssignmentBackend("foobar")
        self.assertEqual("foobar", backend.create_node(None, None))
        self.assertEqual("foobar", backend.get_node(None, None))

    def test_default_node_assignment_backend_reads_configuration(self):
        # monkeypatch pyramid get_current_registry to return our dict
        def patched_registry():
            reg = {}
            setattr(reg, 'settings', {'tokenserver.service_entry': 'yay'})
            return reg

        _registry = backends.get_current_registry
        backends.get_current_registry = patched_registry

        try:
            backend = DefaultNodeAssignmentBackend("yay")
            self.assertEqual("yay", backend.create_node(None, None))
            self.assertEqual("yay", backend.get_node(None, None))

        finally:
            backends.get_current_registry = _registry

    def test_ldap_node_assignment_backend(self):
        ldap = "ldap://user:password@server"
        sreg = "http://to.sreg.server"
        snode = "http://to.snode.server"
        backend = LDAPNodeAssignmentBackend(ldap, sreg, snode, None)

        # in case we esplicitely ask for an unknown user, we return None
        backend.get_node(email, service)

        # in this case, adding an user makes a call to sreg
        node = backend.create_node(email, service)
