from funkload.FunkLoadTestCase import FunkLoadTestCase
from tokenserver.tests.support import get_assertion
import time


class NodeAssignmentTest(FunkLoadTestCase):
    """This tests the assertion verification + node retrieval.

    Depending on the setup of the system under load, it could also test the
    node allocation mechanism.

    You can populate the database of the system under load with the
    "populate-db" script.
    """
    def setUp(self):
        self.root = self.conf_get('main', 'url')
        self.token_exchange = '/1.0/aitc/1.0'
        self.vusers = int(self.conf_get('main', 'vusers'))
        self.valid_domain = 'loadtest.local'
        self.invalid_domain = 'mozilla.com'

    def _do_token_exchange(self, assertion, status=200):
            self.setHeader('Authorization', 'Browser-ID %s' % assertion)
            res = self.get(self.root + self.token_exchange, ok_codes=[status])
            self.assertEquals(res.code, status)
            return res

    def test_token_exchange(self):
        # a valid browserid assertion should be taken by the server and turned
        # back into an authentication token which is valid for 30 minutes.
        # we want to test this for a number of users, with different
        # assertions.
        for idx in range(self.vusers):
            email = "{uid}@{host}".format(uid=idx, host=self.valid_domain)
            self._do_token_exchange(get_assertion(email,
                                                  issuer=self.valid_domain))

    def test_bad_assertions(self):
        # similarly, try to send out bad assertions for the defined virtual
        # users.
        in_one_day = int(time.time() + 60 * 60 * 24) * 1000
        for idx in range(self.vusers):
            email = "{uid}@{host}".format(uid=idx, host=self.valid_domain)

            # expired assertion
            expired = get_assertion(email, issuer=self.valid_domain,
                                    exp=int(time.time() - 60) * 1000)
            self._do_token_exchange(expired, 401)

            # wrong issuer
            wrong_issuer = get_assertion(email, exp=in_one_day)
            self._do_token_exchange(wrong_issuer, 401)

            # wrong email host
            email = "{uid}@{host}".format(uid=idx, host=self.invalid_domain)
            wrong_email_host = get_assertion(email, issuer=self.valid_domain,
                                             exp=in_one_day)
            self._do_token_exchange(wrong_email_host, 401)


if __name__ == '__main__':
    import unittest
    unittest.main()
