import os

from pyramid import testing
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver.assignment import INodeAssignment
from tokenserver import read_endpoints
from tokenserver.tests.support import unittest


_SERVICE = 'sync-1.0'


class TestShardedNode(unittest.TestCase):

    def setUp(self):
        super(TestShardedNode, self).setUp()

        # get the options from the config
        self.config = testing.setUp()
        self.ini = os.path.join(os.path.dirname(__file__),
                                'test_sharded.ini')
        settings = {}
        load_into_settings(self.ini, settings)
        self.config.add_settings(settings)

        # instantiate the backend to test
        self.config.include("tokenserver")
        load_and_register("tokenserver", self.config)
        self.backend = self.config.registry.getUtility(INodeAssignment)

        # adding a service and a node with 100 slots
        self.backend.add_service(_SERVICE, "{node}/{version}/{uid}")
        self.backend.add_node(_SERVICE, "https://phx12", 100)

        self._sqlite = self.backend._dbs['sync'][0].driver == 'pysqlite'
        read_endpoints(self.config)

    def tearDown(self):
        for val in self.backend._dbs.values():
            engine = val[0]
            if engine.driver == 'pysqlite':
                sqluri = str(engine.url)
                filename = sqluri.split('sqlite://')[-1]
                if os.path.exists(filename):
                    os.remove(filename)
            else:
                engine.execute('delete from services')
                engine.execute('delete from nodes')
                engine.execute('delete from users')

    def test_get_node(self):
        user = self.backend.get_user(_SERVICE, "tarek@mozilla.com")
        self.assertEquals(user, None)

        user = self.backend.create_user(_SERVICE, "tarek@mozilla.com")
        self.assertEqual(user['email'], "tarek@mozilla.com")
        self.assertEqual(user['node'], "https://phx12")

        user = self.backend.get_user(_SERVICE, "tarek@mozilla.com")
        self.assertEqual(user['email'], "tarek@mozilla.com")
        self.assertEqual(user['node'], "https://phx12")
