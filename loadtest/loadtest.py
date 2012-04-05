from funkload.FunkLoadTestCase import FunkLoadTestCase

from assertions import (VALID_ASSERTION, WRONG_ISSUER_ASSERTION,
                        WRONG_EMAIL_HOST_ASSERTION, EXPIRED_TOKEN)


class NodeAssignmentTest(FunkLoadTestCase):

    def setUp(self):
        self.root = self.conf_get('main', 'url')
        self.token_exchange = '/1.0/aitc/1.0'

    def _do_token_exchange(self, assertion=None, status=200):
        self.setHeader('Authorization', 'Browser-ID %s' % assertion)
        res = self.get(self.root + self.token_exchange)
        self.assertEquals(res.code, status)
        return res

    def test_token_exchange(self):
        # a valid browserid assertion should be taken by the server and turned
        # back into an authentication token which is valid for 30 minutes.
        self._do_token_exchange(VALID_ASSERTION, 200)

    def test_bad_assertions(self):
        self._do_token_exchange(WRONG_EMAIL_HOST_ASSERTION, 401)
        self._do_token_exchange(EXPIRED_TOKEN, 401)
        self._do_token_exchange(WRONG_ISSUER_ASSERTION, 401)

if __name__ == '__main__':
    import unittest
    unittest.main()
