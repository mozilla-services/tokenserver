from unittest2 import TestCase
import os

from pyramid import testing
from pyramid.threadlocal import get_current_registry
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver.assignment import INodeAssignment
from tokenserver import load_endpoints


class TestSQLBackend(TestCase):

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

        # adding a node with 100 slots
        self.backend._safe_execute(
              """insert into nodes (`node`, `service`, `available`,
                    `capacity`, `current_load`, `downed`, `backoff`)
                  values ("https://phx12", "sync-1.0", 100, 100, 0, 0, 0)""")
        self.backend._safe_execute(
                """insert into service_pattern
                (`service`, `pattern`)
                values
                ("sync-1.0", "{node}/{version}/{uid}")""")
        self._sqlite = self.backend._engine.driver == 'pysqlite'

        endpoints = {}
        load_endpoints(endpoints, self.config)
        get_current_registry()['endpoints_patterns'] = endpoints

    def tearDown(self):
        if self._sqlite:
            filename = self.backend.sqluri.split('sqlite://')[-1]
            if os.path.exists(filename):
                os.remove(filename)
        else:
            self.backend._safe_execute('delete from nodes')
            self.backend._safe_execute('delete from user_nodes')
            self.backend._safe_execute('delete from service_pattern')

    def test_get_node(self):
        unassigned = None, None
        self.assertEquals(unassigned,
                          self.backend.get_node("tarek@mozilla.com",
                              "sync-1.0"))

        res = self.backend.allocate_node("tarek@mozilla.com", "sync-1.0")

        if self._sqlite:
            wanted = (1, u'https://phx12')
        else:
            wanted = (0, u'https://phx12')

        self.assertEqual(res, wanted)
        self.assertEqual(wanted,
                         self.backend.get_node("tarek@mozilla.com", "sync-1.0",
                             ))

    def test_get_patterns(self):
        # patterns should have been populated
        patterns = get_current_registry()['endpoints_patterns']

        self.assertDictEqual(patterns,
                {'sync-1.0': '{node}/{version}/{uid}'})
