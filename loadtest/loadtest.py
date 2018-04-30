
import os
import json
import time
import uuid
import random
import urlparse

import browserid
import browserid.jwt
from browserid.tests.support import make_assertion

from tokenserver.verifiers import DEFAULT_OAUTH_SCOPE

from loads import TestCase


ONE_YEAR = 60 * 60 * 24 * 365


# We use a custom mockmyid site to synthesize valid assertions.
# It's hosted in a static S3 bucket so we don't swamp the live mockmyid server.
MOCKMYID_DOMAIN = "mockmyid.s3-us-west-2.amazonaws.com"
MOCKMYID_PRIVATE_KEY = browserid.jwt.DS128Key({
    "algorithm": "DS",
    "x": "385cb3509f086e110c5e24bdd395a84b335a09ae",
    "y": "738ec929b559b604a232a9b55a5295afc368063bb9c20fac4e53a74970a4db795"
         "6d48e4c7ed523405f629b4cc83062f13029c4d615bbacb8b97f5e56f0c7ac9bc1"
         "d4e23809889fa061425c984061fca1826040c399715ce7ed385c4dd0d40225691"
         "2451e03452d3c961614eb458f188e3e8d2782916c43dbe2e571251ce38262",
    "p": "ff600483db6abfc5b45eab78594b3533d550d9f1bf2a992a7a8daa6dc34f8045a"
         "d4e6e0c429d334eeeaaefd7e23d4810be00e4cc1492cba325ba81ff2d5a5b305a"
         "8d17eb3bf4a06a349d392e00d329744a5179380344e82a18c47933438f891e22a"
         "eef812d69c8f75e326cb70ea000c3f776dfdbd604638c2ef717fc26d02e17",
    "q": "e21e04f911d1ed7991008ecaab3bf775984309c3",
    "g": "c52a4a0ff3b7e61fdf1867ce84138369a6154f4afa92966e3c827e25cfa6cf508b"
         "90e5de419e1337e07a2e9e2a3cd5dea704d175f8ebf6af397d69e110b96afb17c7"
         "a03259329e4829b0d03bbc7896b15b4ade53e130858cc34d96269aa89041f40913"
         "6c7242a38895c9d5bccad4f389af1d7a4bd1398bd072dffa896233397a",
})


# There are three different kinds of test, one of which is randomly
# selected for each run:
#
#    - get a token for a previously-seen user
#    - get a token for a never-before-seen user
#    - fail to get a token using an invalid assertion
#
# The first is the default operation and by far the most likely.
# The below options control what percentage of the requests are each
# of the other types.

PERCENT_NEW_USER = 0.3  # point-three of one percent; yes really
PERCENT_BAD_USER = 1.0

# There are two different authentication mechanisms that can be used,
# either BrowserID assertions or FxA OAuth tokens.  The below option
# controls what proportion of requests are the later.

PERCENT_OAUTH = 5.0  # we expect very low OAuth traffic initially


class NodeAssignmentTest(TestCase):
    """This tests the assertion verification + node retrieval.

    It sends a combination of existing-user, new-user, and invalid-assertion
    requests and does some basic sanity-checking on the results.
    """

    server_url = 'https://token.stage.mozaws.net'

    def setUp(self):
        self.endpoint = urlparse.urljoin(self.server_url, '/1.0/sync/1.5')
        self.audience = self.server_url.rstrip('/')

    def test_server_config(self):
        """Sanity-check server config against local settings.

        This is a quick test that fetches config from the target server
        and checks it against our local settings.  It will fail if there's
        a mis-match that would cause our loatests to fail.
        """
        res = self.session.get(self.server_url + '/')
        self.assertEquals(res.status_code, 200)
        server_config = res.json()
        try:
            allowed_issuers = server_config['browserid']['allowed_issuers']
            if allowed_issuers is not None:
                if MOCKMYID_DOMAIN not in allowed_issuers:
                    msg = 'Server does not allow browserid assertions from {}'
                    raise AssertionError(msg.format(MOCKMYID_DOMAIN))
        except KeyError:
            pass
        if server_config['oauth']['default_issuer'] != MOCKMYID_DOMAIN:
            msg = 'OAuth default_issuer does not match {}'
            raise AssertionError(msg.format(MOCKMYID_DOMAIN))
        if server_config['oauth']['scope'] != DEFAULT_OAUTH_SCOPE:
            msg = 'OAuth scope does not match {}'
            raise AssertionError(msg.format(DEFAULT_OAUTH_SCOPE))

    def test_realistic(self):
        """Run a test scencario based on 'realistic' user behaviour.

        The 'realistic' part depends on correctly configuring the ratio
        of various kinds of events in the global variables above, to match
        observed user behaviour in production.
        """
        if self._flip_a_coin(PERCENT_BAD_USER):
            self._test_bad_auth()
        elif self._flip_a_coin(PERCENT_NEW_USER):
            self._test_new_user()
        else:
            self._test_old_user()

    def _make_assertion(self, email, **kwds):
        if "audience" not in kwds:
            kwds["audience"] = self.audience
        if "exp" not in kwds:
            kwds["exp"] = int((time.time() + ONE_YEAR) * 1000)
        if "issuer" not in kwds:
            kwds["issuer"] = MOCKMYID_DOMAIN
        if "issuer_keypair" not in kwds:
            kwds["issuer_keypair"] = (None, MOCKMYID_PRIVATE_KEY)
        return make_assertion(email, **kwds)

    def _make_oauth_token(self, user=None, status=200, **fields):
        # For mock oauth tokens, we bundle the desired status code
        # and response body into a JSON blob for the mock verifier
        # to echo back to us.
        body = {}
        if status < 400:
            if user is None:
                raise ValueError("Must specify user for valid oauth token")
            if "scope" not in fields:
                fields["scope"] = [DEFAULT_OAUTH_SCOPE]
            if "client_id" not in fields:
                fields["client_id"] = "x"
        if user is not None:
            parts = user.split("@", 1)
            if len(parts) == 1:
                body["user"] = user
            else:
                body["user"] = parts[0]
                body["issuer"] = parts[1]
        body.update(fields)
        return json.dumps({
          "status": status,
          "body": body
        })

    def _do_token_exchange_via_browserid(self, assertion, status=200):
        headers = {'Authorization': 'BrowserID %s' % assertion}
        res = self.session.get(self.endpoint, headers=headers)
        self.assertEquals(res.status_code, status)
        return res

    def _do_token_exchange_via_oauth(self, token, status=200):
        headers = {'Authorization': 'Bearer %s' % token}
        res = self.session.get(self.endpoint, headers=headers)
        self.assertEquals(res.status_code, status)
        return res

    def _do_token_exchange(self, email):
        if self._flip_a_coin(PERCENT_OAUTH):
            self._do_token_exchange_via_oauth(self._make_oauth_token(email))
        else:
            self._do_token_exchange_via_browserid(self._make_assertion(email))

    def _test_old_user(self):
        # Get a token for an "existing" user account.
        # There's no guarantee it will actually exist, but we pull from a
        # fixed pool of user ids so they should get created and persist
        # over time.
        uid = random.randint(1, 1000000)
        email = "user{uid}@{host}".format(uid=uid, host=MOCKMYID_DOMAIN)
        self._do_token_exchange(email)

    def _test_new_user(self):
        # Get a token for a never-before-seen user account.
        uid = str(uuid.uuid1())
        email = "loadtest-{uid}@{host}".format(uid=uid, host=MOCKMYID_DOMAIN)
        self._do_token_exchange(email)

    def _test_bad_auth(self):
        if self._flip_a_coin(PERCENT_OAUTH):
            self._test_bad_oauth_token()
        else:
            self._test_bad_assertion()

    def _test_bad_assertion(self):
        uid = random.randint(1, 1000000)
        # Try to get a token using an invalid assertion.
        # Obviously, this should result in a 401.
        if self._flip_a_coin(25):
            # expired assertion
            assertion = self._make_assertion(
                "{uid}@{host}".format(uid=uid, host=MOCKMYID_DOMAIN),
                exp=int(time.time() - ONE_YEAR) * 1000
            )
        elif self._flip_a_coin(25):
            # email/issuer mismatch
            assertion = self._make_assertion(
                "{uid}@hotmail.com".format(uid=uid)
            )
        elif self._flip_a_coin(25):
            # invalid issuer privkey
            assertion = self._make_assertion(
                "{uid}@{host}".format(uid=uid, host=MOCKMYID_DOMAIN),
                issuer="api.accounts.firefox.com"
            )
        else:
            # invalid audience
            assertion = self._make_assertion(
                "{uid}@{host}".format(uid=uid, host=MOCKMYID_DOMAIN),
                audience="http://123done.org"
            )
        self._do_token_exchange_via_browserid(assertion, 401)

    def _test_bad_oauth_token(self):
        uid = random.randint(1, 1000000)
        # Try to get a token using an invalid OAuth token.
        # Obviously, this should result in a 401.
        if self._flip_a_coin(50):
            # invalid token
            token = self._make_oauth_token(status=400, errno=108)
        else:
            # invalid scope
            token = self._make_oauth_token(
                user=str(uid),
                scope=["unrelated", "scopes"],
            )
        self._do_token_exchange_via_oauth(token, 401)

    def _flip_a_coin(self, percent=50):
        # Return True on 'percent' percent of calls.
        return (random.random() * 100) < percent
