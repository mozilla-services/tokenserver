import json
import unittest
from browserid import DummyVerifier

#import patch

from funkload.FunkLoadTestCase import FunkLoadTestCase


class SimpleTest(FunkLoadTestCase):

    def setUp(self):
        self.root = self.conf_get('main', 'url')
        self.vusers = int(self.conf_get('main', 'vusers'))
        self.verifier = DummyVerifier
        key = DummyVerifier.fetch_public_key("browserid.org")
        key = json.dumps({"public-key": key})

        def urlopen(url, data): # NOQA
            class response(object):
                @staticmethod
                def read():
                    return key
            return response

        self.verifier.urlopen = urlopen

    def _getassertion(self):
        email = 'tarek@mozilla.com'
        url = 'http://tokenserver.services.mozilla.com'
        return self.verifier.make_assertion(email, url)

    def test_simple(self):
        # get a token
        # GET /1.0/simple_storage/2.0
        assertion = self._getassertion()
        self.setHeader('Authorization', 'Browser-ID %s' % assertion)
        res = self.get(self.root + '/1.0/sync/1.0')
        self.assertEquals(res.code, 200)


if __name__ == '__main__':
    unittest.main()
