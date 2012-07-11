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

        # adding a node with 100 slots

        self.backend._safe_execute(
              """insert into nodes (`node`, `service`, `available`,
                    `capacity`, `current_load`, `downed`, `backoff`)
                  values ("https://phx12", "sync-1.0", 100, 100, 0, 0, 0)""",
                  service=_SERVICE)

        self.backend._safe_execute(
                """insert into service_pattern
                (`service`, `pattern`)
                values
                ("sync-1.0", "{node}/{version}/{uid}")""",
                service="sync-1.0")

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
                engine.execute('delete from nodes')
                engine.execute('delete from user_nodes')
                engine.execute('delete from service_pattern')

    def test_get_node(self):
        unassigned = None, None, None
        self.assertEquals(unassigned,
                          self.backend.get_node("tarek@mozilla.com", _SERVICE,
                                                ))

        res = self.backend.allocate_node("tarek@mozilla.com", _SERVICE)

        if self._sqlite:
            wanted = (1, u'https://phx12')
        else:
            wanted = (0, u'https://phx12')

        self.assertEqual(res, wanted)
        self.assertEqual(wanted + (None,),
                         self.backend.get_node("tarek@mozilla.com", _SERVICE))
