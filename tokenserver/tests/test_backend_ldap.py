from unittest2 import TestCase
import os

from pyramid import testing
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver import logger
from tokenserver.backend import INodeAssignment
from tokenserver.tests.support import (MemoryStateConnector, RegPatcher,
                                       LDAP_SUPPORT)


if not LDAP_SUPPORT:
    logger.warning('**** NO LDAP SUPPORT - NOT TESTING LDAP BACKEND *****')
else:
    class TestLDAPNode(TestCase, RegPatcher):

        def setUp(self):
            # get the options from the config
            self.config = testing.setUp()
            self.ini = os.path.join(os.path.dirname(__file__),
                                    'test_ldapnode.ini')
            settings = {}
            load_into_settings(self.ini, settings)
            self.config.add_settings(settings)

            # instantiate the backend to test
            self.config.include("tokenserver")
            load_and_register("tokenserver", self.config)
            self.backend = self.config.registry.getUtility(INodeAssignment)
            self.backend.pool.connector_cls = MemoryStateConnector
            super(TestLDAPNode, self).setUp()

        def set_return_values(self, key, values):
            MemoryStateConnector.set_return_values(key, values)

        def test_return_right_node(self):
            # if we ask for a particular email/service/version association
            # which
            # exists, we should return it
            data = {
                'cn': 'fvfkealwhrxs2mjhzfngm22m3syphxzn',
                'sn': 'fvfkealwhrxs2mjhzfngm22m3syphxzn',
                'rescueNode': 'weave',
                'uid': 'fvfkealwhrxs2mjhzfngm22m3syphxzni',
                'uidNumber': '3000000',
                'mail-verified': '28331b90cfdc4627f1097f7bc3b311c8f8da9ea5',
                'account-enabled': 'Yes',
                'mail': 'alexis@mozilla.com',
                'objectClass': 'dataStore',
                'objectClass': 'inetOrgPerson',
                'primaryNode': 'weave:phx-sync437.services.mozilla.com',
                'syncNode': 'phx-sync437.services.mozilla.com',
            }
            self.set_return_values(
                    "mail=alexis@mozilla.com,ou=users,dc=mozilla", data)

            self.assertEquals(data['primaryNode'],
                self.backend.get_node("alexis@mozilla.com", "sync")[0])

        def test_return_none_when_unknown(self):
            # if there is no record of the wanted user, the backend should
            # return a hash
            self.assertEquals((None, None),
                    self.backend.get_node("alexis@mozilla.com", "sync"))

            # when asking for an associaiton which isn't existing, the backend
            # should return None
            self.set_return_values(
                "mail=alexis@mozilla.com,ou=users,dc=mozilla", {
                # this data misses the primaryNode key
                'cn': 'fvfkealwhrxs2mjhzfngm22m3syphxzn',
                'sn': 'fvfkealwhrxs2mjhzfngm22m3syphxzn',
                'rescueNode': 'weave',
                'uid': 'fvfkealwhrxs2mjhzfngm22m3syphxzni',
                'uidNumber': '3000000',
                'mail-verified': '28331b90cfdc4627f1097f7bc3b311c8f8da9ea5',
                'account-enabled': 'Yes',
                'mail': 'alexis@mozilla.com',
                'objectClass': 'dataStore',
            })

            node, username = self.backend.get_node("alexis@mozilla.com",
                                                   "sync")
            self.assertEquals(node, None)
            self.assertNotEqual(username, None)
