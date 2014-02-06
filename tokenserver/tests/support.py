import os

from browserid.verifiers.local import LocalVerifier
from browserid.tests.support import (make_assertion, get_keypair,
                                     patched_supportdoc_fetching)

from powerhose.job import Job
from tokenserver.crypto.master import PowerHoseRunner
from tokenserver.crypto.pyworker import CryptoWorker, get_crypto_worker

# if unittest2 isn't available, assume that we are python 2.7
try:
    import unittest2 as unittest
except:
    import unittest  # NOQA


# very dummy verifier
class DummyVerifier(LocalVerifier):
    def verify_certificate_chain(self, certs, *args, **kw):
        return certs[0]


CERTS_LOCATION = os.path.join(os.path.dirname(__file__), 'certs')


def load_key(hostname):
    return get_keypair(hostname)[1]


def sign_data(hostname, data, key=None):
    # load the cert with the private key
    return load_key(hostname).sign(data)


class PurePythonRunner(PowerHoseRunner):
    def __init__(self, runner=None, **kwargs):
        if runner is None:
            runner = get_crypto_worker(CryptoWorker, **kwargs)
        self.runner = runner

        def patched_runner(job):
            return self.runner(Job(job))

        setattr(self, 'execute', patched_runner)


class MockCryptoWorker(CryptoWorker):
    """Test implementation of the crypto worker, using the patched certificate
    handling.
    """
    def __init__(self, *args, **kwargs):
        super(MockCryptoWorker, self).__init__(*args, **kwargs)

    def check_signature(self, *args, **kwargs):
        with patched_supportdoc_fetching():
            return super(MockCryptoWorker, self)\
                .check_signature(*args, **kwargs)


def get_assertion(email, audience="*", issuer='browserid.org',
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

    assertion = make_assertion(email, audience, issuer=issuer, **kwargs)
    return assertion.encode('ascii')
