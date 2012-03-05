from unittest2 import TestCase
import os

from pyramid import testing
from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register
from sqlalchemy.exc import IntegrityError

from tokenserver import logger
from tokenserver.assignment import INodeAssignment


class TestShardedNode(TestCase):

    def setUp(self):
        super(TestCase, self).setUp()

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
        self.backend._safe_execute('sync',
              """insert into nodes (`node`, `service`, `available`,
                    `capacity`, `current_load`, `downed`, `backoff`)
                  values ("phx12", "sync", 100, 100, 0, 0, 0)""")

        self._sqlite = self.backend._dbs['sync'][0].driver == 'pysqlite'

    def tearDown(self):
        for engine, __, __ in self.backend._dbs.values():
            if engine.driver == 'pysqlite':
                sqluri = str(engine.url)
                filename = sqluri.split('sqlite://')[-1]
                if os.path.exists(filename):
                    os.remove(filename)
            else:
                engine.execute('delete from nodes')
                engine.execute('delete from user_nodes')

    def test_get_node(self):

        unassigned = None, None
        self.assertEquals(unassigned,
                          self.backend.get_node("tarek@mozilla.com", "sync"))

        res = self.backend.allocate_node("tarek@mozilla.com", "sync")

        if self._sqlite:
            wanted = (1, u'phx12')
        else:
            wanted = (0, u'phx12')

        self.assertEqual(res, wanted)
        self.assertEqual(wanted,
                         self.backend.get_node("tarek@mozilla.com", "sync"))
