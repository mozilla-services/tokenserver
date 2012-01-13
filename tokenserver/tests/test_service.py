from webtest import TestApp
import unittest

from tokenserver import main


class TestService(unittest.TestCase):

    def test_case(self):
        app = TestApp(main({}))
        app.get('/1.0/sync/token', status=401)
