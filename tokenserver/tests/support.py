import urllib2
import json
import random
import time
import os
from contextlib import contextmanager

from browserid.verifiers.local import LocalVerifier
from browserid.tests.support import (make_assertion, get_keypair,
                                     patched_key_fetching)

from powerhose.job import Job
from tokenserver.crypto.master import PowerHoseRunner
from tokenserver.crypto.pyworker import CryptoWorker

# if unittest2 isn't available, assume that we are python 2.7
try:
    import unittest2 as unittest
except:
    import unittest  # NOQA

try:
    import ldap
    from ldappool import StateConnector
    LDAP_SUPPORT = True
except ImportError:
    LDAP_SUPPORT = False


class _Resp(object):
    def __init__(self, data='', code=200):
        self.data = data
        self.code = code
        self.headers = {}

    def read(self):
        return self.data

    def getcode(self):
        return self.code


# very dummy verifier
class DummyVerifier(LocalVerifier):
    def verify_certificate_chain(self, certs, *args, **kw):
        return certs[0]


# drop-in replacement for the default connector for ldappool
if LDAP_SUPPORT:
    class MemoryStateConnector(StateConnector):

        return_values = None

        def __init__(self, uri, bind=None, passwd=None, **kw):
            if bind is not None and passwd is not None:
                self.simple_bind_s(bind, passwd)
            self.uri = uri
            self._next_id = 30
            self._l = self

        def get_lifetime(self):
            return time.time()

        def unbind_ext(self, *args, **kw):
            if random.randint(1, 10) == 1:
                raise ldap.LDAPError('Invalid State')

        def simple_bind_s(self, who, passwd):
            self.connected = True
            self.who = who
            self.cred = passwd

        def search_st(self, dn, *args, **kw):
            if self.__class__.return_values is not None:
                values = [self.__class__.return_values]
                self.__class__.return_values = None
                return values
            return ()

        @classmethod
        def set_return_values(cls, request, values):
            cls.return_values = (request, values)
else:
    MemoryStateConnector = None


class RegPatcher(object):

    def _response(self, req, *args, **kw):
        url = req.get_full_url()
        if not url.endswith('sync'):
            res = 'kismw365lo7emoxr3ohojgpild6lph4b'
        else:
            res = 'http://phx324'

        return _Resp(json.dumps(res))

    def setUp(self):
        self.old = urllib2.urlopen
        urllib2.urlopen = self._response
        super(RegPatcher, self).setup()

    def tearDown(self):
        urllib2.urlopen = self.old
        super(RegPatcher, self).tearDown()


CERTS_LOCATION = os.path.join(os.path.dirname(__file__), 'certs')


def load_key(hostname):
    return get_keypair(hostname)[1]


def sign_data(hostname, data, key=None):
    # load the cert with the private key
    return load_key(hostname).sign(data)


class PurePythonRunner(PowerHoseRunner):
    def __init__(self, runner):
        self.runner = runner

        def patched_runner(job):
            return self.runner(Job(job))

        setattr(self, 'execute', patched_runner)


@contextmanager
def patched_environ():
    os.environ['MEMORY_TTL'] = '3600'
    yield
    del os.environ['MEMORY_TTL']


class MockCryptoWorker(CryptoWorker):
    """Test implementation of the crypto worker, using the patched certificate
    handling.
    """
    def __init__(self, *args, **kwargs):
        super(MockCryptoWorker, self).__init__(*args, **kwargs)

    def check_signature(self, *args, **kwargs):
        with patched_key_fetching():
            return super(MockCryptoWorker, self)\
                    .check_signature(*args, **kwargs)


def get_assertion(email, audience='*', issuer='browserid.org',
        bad_issuer_cert=False, bad_email_cert=False, exp=None):
    """Creates a browserid assertion for the given email, audience and
    hostname.

    This function can also be used to create invalid assertions. This will be
    the case if you set the bad_issuer_cert or the bad_email cert arguments to
    True.
    """
    kwargs = {'exp': exp}
    if bad_issuer_cert:
        kwargs['issuer_keypair'] =\
                get_keypair(hostname="not-the-right-host.com")

    if bad_email_cert:
        kwargs['email_keypair'] =\
                get_keypair(hostname="not-the-right-host.com")

    return make_assertion(email, audience, issuer=issuer, **kwargs)
