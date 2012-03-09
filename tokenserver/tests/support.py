import urllib2
import json
import random
import time
import os

from vep.verifiers.local import LocalVerifier
from vep import jwt

from tokenserver.crypto.pyworker import _RSA
from tokenserver.crypto.master import PowerHoseRunner

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
    filename = os.path.join(CERTS_LOCATION, '%s.key' % hostname)
    obj = _RSA.load_key(filename)
    return jwt.RS256Key(obj=obj)


def sign_data(hostname, data, key=None):
    # load the cert with the private key
    return load_key(hostname).sign(data)


class PurePythonRunner(PowerHoseRunner):
    def __init__(self, runner):
        self.runner = runner

        def patched_runner(blah, data):
            return self.runner(data)

        setattr(self.runner, 'execute', patched_runner)
