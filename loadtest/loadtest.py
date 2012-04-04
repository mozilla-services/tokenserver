from funkload.FunkLoadTestCase import FunkLoadTestCase

from assertions import VALID, WRONG_ISSUER, WRONG_EMAIL_HOST

DEFAULT_EMAIL = 'alexis@loadtest.localdomain'


class SimpleTest(FunkLoadTestCase):

    def setUp(self):
        self.root = self.conf_get('main', 'url')

    def _do_token_exchange(self, assertion=None, status=200):
        self.setHeader('Authorization', 'Browser-ID %s' % assertion)
        res = self.get(self.root + self.token_exchange)
        self.assertEquals(res.code, status)
        return res

    def test_token_exchange(self):
        # a valid browserid assertion should be taken by the server and turned
        # back into an authentication token which is valid for 30 minutes.
        self._do_token_exchange(VALID, 200)

    def test_bad_assertions(self):
        # a wrong certificate should return a 400 error
        self._do_token_exchange(WRONG_ISSUER, 400)

        # a wrong issuer cert as well
        self._do_token_exchange(WRONG_EMAIL_HOST, 200)

if __name__ == '__main__':
    import unittest
    unittest.main()
