from webtest import TestApp
import unittest
import json

from tokenserver import main


class TestService(unittest.TestCase):

    def test_unknown_app(self):
        app = TestApp(main({}))
        res = app.get('/1.0/xXx/token', status=404)
        res = json.loads(res.body)
        self.assertEqual(res['errors'][0], 'Unknown application')

    def test_case(self):
        app = TestApp(main({}))
        app.get('/1.0/sync/token', status=401)
