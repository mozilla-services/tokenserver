import os

from browserid.verifiers.local import LocalVerifier
from browserid.tests.support import (make_assertion, get_keypair)


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
