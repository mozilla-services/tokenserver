import unittest

from tokenserver.tests.support import get_assertion
from funkload.FunkLoadTestCase import FunkLoadTestCase


class SimpleTest(FunkLoadTestCase):

    def setUp(self):
        self.root = self.conf_get('main', 'url')
        self.vusers = int(self.conf_get('main', 'vusers'))
        #self.certs = CertificatesManager()
        #key = self.certs.fetch_public_key("browserid.org")
        #key = json.dumps({"public-key": key})

    def _getassertion(self):
        email = 'tarek@mozilla.com'
        return get_assertion(email)

    def test_simple(self):
        # get a token
        # GET /1.0/simple_storage/2.0
        assertion = self._getassertion()
        self.setHeader('Authorization', 'Browser-ID %s' % assertion)
        res = self.get(self.root + '/1.0/aitc/1.0')
        self.assertEquals(res.code, 200)


if __name__ == '__main__':
    unittest.main()
