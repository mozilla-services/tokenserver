from webtest import TestApp
import unittest
import json

from tokenserver import main
from vep import DummyVerifier


class TestService(unittest.TestCase):

    def setUp(self):
        self.verifier = DummyVerifier

        def urlopen(url, data): # NOQA
            class response(object):
                @staticmethod
                def read():
                    key = DummyVerifier.fetch_public_key("browserid.org")
                    return json.dumps({"public-key": key})
            return response

        self.verifier.urlopen = urlopen

    def _getassertion(self):
        email = 'tarek@mozilla.com'
        url = 'http://tokenserver.services.mozilla.com'
        return self.verifier.make_assertion(email, url)

    def test_unknown_app(self):
        app = TestApp(main({}))
        headers = {'Authorization': 'Browser-ID %s' % self._getassertion()}
        res = app.get('/1.0/xXx/token', headers=headers, status=404)
        res = json.loads(res.body)
        self.assertEqual(res['errors'][0], 'Unknown application')

    def test_no_auth(self):
        app = TestApp(main({}))
        app.get('/1.0/sync/token', status=401)
