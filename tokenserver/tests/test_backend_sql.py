import os
import unittest

from pyramid import testing
from pyramid.threadlocal import get_current_registry
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register
from sqlalchemy.exc import IntegrityError

from tokenserver.assignment import INodeAssignment
from tokenserver import load_endpoints


class TestSQLBackend(unittest.TestCase):

    def setUp(self):
        super(TestSQLBackend, self).setUp()

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

        # adding a service and a node with 100 slots
        try:
            self.backend.add_service("sync-1.1", "{node}/1.1/{uid}")
        except IntegrityError:
            # ignore if the service was already added by another test.
            pass
        self.backend.add_node("sync-1.1", "https://phx12", 100, nodeid=0)

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
            self.backend._safe_execute('delete from services')
            self.backend._safe_execute('delete from nodes')
            self.backend._safe_execute('delete from users')

    def test_get_node(self):
        user = self.backend.get_user("sync-1.1", "test1@example.com")
        self.assertEquals(user, None)

        user = self.backend.allocate_user("sync-1.1", "test1@example.com", )
        self.assertEqual(user['email'], "test1@example.com")
        self.assertEqual(user['node'], "https://phx12")

        user = self.backend.get_user("sync-1.1", "test1@example.com")
        self.assertEqual(user['email'], "test1@example.com")
        self.assertEqual(user['node'], "https://phx12")

    def test_get_patterns(self):
        # patterns should have been populated
        patterns = get_current_registry()['endpoints_patterns']
        self.assertDictEqual(patterns, {'sync-1.1': '{node}/1.1/{uid}'})
