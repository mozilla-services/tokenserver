from unittest2 import TestCase
import os

from pyramid import testing
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver import logger
from tokenserver.assignment import INodeAssignment


class TestLDAPNode(TestCase):

    def setUp(self):
        super(TestCase, self).setUp()

        # get the options from the config
        self.config = testing.setUp()
        self.ini = os.path.join(os.path.dirname(__file__),
                                'test_sql.ini')
        settings = {}
        load_into_settings(self.ini, settings)
        self.config.add_settings(settings)

        # instantiate the backend to test
        self.config.include("tokenserver")
        load_and_register("tokenserver", self.config)
        self.backend = self.config.registry.getUtility(INodeAssignment)

    def tearDown(self):
        filename = self.backend.sqluri.split('sqlite://')[-1]
        if os.path.exists(filename):
            os.remove(filename)

    def test_get_node(self):

        unassigned = None, None
        self.assertEquals(unassigned,
                          self.backend.get_node("tarek@mozilla.com", "sync"))

        res = self.backend.create_node("tarek@mozilla.com", "sync")
        wanted = (1, u'phx12')
        self.assertEqual(res, wanted)
        self.assertEqual(wanted,
                         self.backend.get_node("tarek@mozilla.com", "sync"))
