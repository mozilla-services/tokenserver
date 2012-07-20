from funkload.FunkLoadTestCase import FunkLoadTestCase
import time
import browserid
import browserid.jwt
from browserid.tests.support import make_assertion
import random
import uuid


MOCKMYID_PRIVATE_KEY = browserid.jwt.RS256Key({
  "algorithnm": "RS",
  "n": "154988747580902760394650941058372315672655463739759604809411226511"\
       "077728241215274831074023538998462524898370248701917073947431963995"\
       "829594255139047629967566720896935410098920308488250796497830860055"\
       "544424902329008757928517862039480884579424169789764552974280774608"\
       "906504095492421246555369861413637195898821600814807850489656862851"\
       "420023207670666748797372380120641566758995125031432254819338645077"\
       "931184578057920644455028341623155321139637468017701876856504085604"\
       "246826549377447138137738969622637096927246306509521595969513482640"\
       "050043750176104418359560732757087402395180114009919728116694933566"\
       "82993446554779893834303",
  "e": "65537",
  "d": "65399069618723544500872440362363672698042543818900958411270855515"\
       "77495913426869112377010004955160417265879626558436936025363204803"\
       "91331858268095155890431830889373003315817865054997037936791585608"\
       "73644285308283967959957813646594134677848534354507623921570269626"\
       "94408807947047846891301466649598749901605789115278274397848888140"\
       "10530606360821777612754992672154421572087230519464512940305680198"\
       "74227941147032559892027555115234340986250008269684300770919843514"\
       "10839837395828971692109391386427709263149504336916566097901771762"\
       "64809088099477332528320749664563079224800780517787353244131447050"\
       "2254528486411726581424522838833"
})


# options to tweak test_realistic
USER_EXIST = 1
USER_NEW = 2
USER_BAD = 3


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
        self.existing = int(self.conf_get('main', 'existing'))
        self.new = int(self.conf_get('main', 'new'))
        self.bad = int(self.conf_get('main', 'bad'))
        self.user_choice = ([USER_EXIST] * self.existing +
          [USER_NEW] * self.new +
          [USER_BAD] * self.bad)
        random.shuffle(self.user_choice)
        self.invalid_domain = 'mozilla.com'
        self.valid_domain = 'mockmyid.com'
        self.audience = self.conf_get('main', 'audience')

    def _do_token_exchange(self, assertion, status=200):
        self.setHeader('Authorization', 'Browser-ID %s' % assertion)
        res = self.get(self.root + self.token_exchange, ok_codes=[status])
        self.assertEquals(res.code, status)
        return res

    def test_single_token_exchange(self):
        uid = random.randint(1, 1000000)
        email = "user{uid}@{host}".format(uid=uid, host=self.valid_domain)
        self._do_token_exchange(make_assertion(
            email=email,
            issuer=self.valid_domain,
            audience=self.audience,
            issuer_keypair=(None, MOCKMYID_PRIVATE_KEY)))

    def test_single_token_exchange_new_user(self):
        uid = str(uuid.uuid1())
        email = "loadtest-{uid}@{host}".format(uid=uid, host=self.valid_domain)
        self._do_token_exchange(make_assertion(
            email=email,
            issuer=self.valid_domain,
            audience=self.audience,
            issuer_keypair=(None, MOCKMYID_PRIVATE_KEY)))

    def test_realistic(self):
        # this test runs as following:
        #   - 95% ask for assertions on existing users (on a DB filled by
        #                                           test_single_token_exchange)
        #   - 4% ask for assertion on a new use
        #   - 1% ask for a bad assertion
        #
        #   Tweak it with the existing, new, bad variables in the conf file
        choice = random.choice(user_choice)
        if choice == USER_EXIST :
            return self.test_single_token_exchange()
        elif choice == USER_NEW:
            return self.test_single_token_exchange_new_user()

        return self._test_bad_assertion()

    def test_token_exchange(self):
        # a valid browserid assertion should be taken by the server and turned
        # back into an authentication token which is valid for 30 minutes.
        # we want to test this for a number of users, with different
        # assertions.
        for idx in range(self.vusers):
            email = "{uid}@{host}".format(uid=idx, host=self.valid_domain)
            self._do_token_exchange(make_assertion(
                email=email,
                issuer=self.valid_domain,
                audience=self.audience,
                issuer_keypair=(None, MOCKMYID_PRIVATE_KEY)))

    def _test_bad_assertion(self, idx=None, in_one_day=None):
        if idx is None:
            idx = random.choice(range(self.vusers))

        if in_one_day is None:
            in_one_day = int(time.time() + 60 * 60 * 24) * 1000
        email = "{uid}@{host}".format(uid=idx, host="mockmyid.com")
        # expired assertion
        expired = make_assertion(
                email=email,
                issuer=self.valid_domain,
                exp=int(time.time() - 60) * 1000,
                audience=self.audience,
                issuer_keypair=(None, MOCKMYID_PRIVATE_KEY))
        self._do_token_exchange(expired, 401)

        # wrong issuer
        wrong_issuer = make_assertion(email, exp=in_one_day,
                                        audience=self.audience)
        self._do_token_exchange(wrong_issuer, 401)

        # wrong email host
        email = "{uid}@{host}".format(uid=idx, host=self.invalid_domain)
        wrong_email_host = make_assertion(
                email, issuer=self.valid_domain,
                exp=in_one_day,
                audience=self.audience,
                issuer_keypair=(None, MOCKMYID_PRIVATE_KEY))
        self._do_token_exchange(wrong_email_host, 401)

    def test_bad_assertions(self):
        # similarly, try to send out bad assertions for the defined virtual
        # users.
        in_one_day = int(time.time() + 60 * 60 * 24) * 1000
        for idx in range(self.vusers):
            self._test_bad_assertion(idx, in_one_day)


if __name__ == '__main__':
    import unittest
    unittest.main()
