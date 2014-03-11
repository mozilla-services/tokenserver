import time
import json

from pyramid.threadlocal import get_current_registry
from zope.interface import implements, Interface

import socket
import requests

from browserid.verifiers.local import LocalVerifier as LocalVerifier_
from browserid.errors import (InvalidSignatureError, ExpiredSignatureError,
                              ConnectionError, AudienceMismatchError,
                              InvalidIssuerError)

from tokenserver.crypto.master import get_runner


def get_verifier():
    """returns the registered verifier, building it if necessary."""
    return get_current_registry().getUtility(IBrowserIdVerifier)


# This is to simplify the registering of the implementations using pyramid
# registry.
class IBrowserIdVerifier(Interface):
    pass


# The default verifier from browserid
class LocalVerifier(LocalVerifier_):
    implements(IBrowserIdVerifier)


# A verifier that posts to a remote verifier service.
# The RemoteVerifier implementation from PyBrowserID does its own parsing
# of the assertion, and hasn't been updated for the new BrowserID formats.
# Rather than blocking on that work, we use a simple work-alike that doesn't
# do any local inspection of the assertion.
class RemoteVerifier(object):
    implements(IBrowserIdVerifier)

    def __init__(self, audiences=None, trusted_issuers=None,
                 allowed_issuers=None, verifier_url=None):
        # Since we don't parse the assertion locally, we cannot support
        # list- or pattern-based audience strings.
        if audiences is not None:
            assert isinstance(audiences, basestring)
        self.audiences = audiences
        if isinstance(trusted_issuers, basestring):
            trusted_issuers = trusted_issuers.split()
        self.trusted_issuers = trusted_issuers
        if isinstance(allowed_issuers, basestring):
            allowed_issuers = allowed_issuers.split()
        self.allowed_issuers = allowed_issuers
        if verifier_url is None:
            verifier_url = "https://verifier.accounts.firefox.com/v2"
        self.verifier_url = verifier_url
        self.session = requests.Session()
        self.session.verify = True

    def verify(self, assertion, audience=None):
        if audience is None:
            audience = self.audiences

        body = {'assertion': assertion, 'audience': audience}
        if self.trusted_issuers is not None:
            body['trustedIssuers'] = self.trusted_issuers
        headers = {'content-type': 'application/json'}
        try:
            response = self.session.post(self.verifier_url,
                                         data=json.dumps(body),
                                         headers=headers)
        except (socket.error, requests.RequestException), e:
            msg = "Failed to POST %s. Reason: %s" % (self.verifier_url, str(e))
            raise ConnectionError(msg)

        if response.status_code != 200:
            raise ConnectionError('server returned invalid response')
        try:
            data = json.loads(response.text)
        except ValueError:
            raise ConnectionError("server returned invalid response")

        if data.get('status') != "okay":
            reason = data.get('reason', 'unknown error')
            if "audience mismatch" in reason:
                raise AudienceMismatchError(data.get("audience"), audience)
            if "expired" in reason or "issued later than" in reason:
                raise ExpiredSignatureError(reason)
            raise InvalidSignatureError(reason)
        if self.allowed_issuers is not None:
            issuer = data.get('issuer')
            if issuer not in self.allowed_issuers:
                raise InvalidIssuerError("Issuer not allowed: %s" % (issuer,))
        return data


class PowerHoseVerifier(LocalVerifier):
    """PyBrowserID verifier using powerhose for cryptographic operations."""

    def __init__(self, *args, **kwargs):
        # At instanciation, this verifier gets the powerhose runner from the
        # registry and use it for the internal operations
        self._runner = kwargs.pop('runner', None)

        super(PowerHoseVerifier, self).__init__(warning=False, *args, **kwargs)

    @property
    def runner(self):
        if self._runner is None:
            self._runner = get_runner()
        return self._runner

    def verify_certificate_chain(self, certificates, now=None):
        """Verify a certificate chain using a powerhose worker.

        The main difference with the base LocalVerifier class is that we
        are using the issuer name as a key to give the information to the
        worker, so we don't need to pass along the certificate.

        In case there is a list of certificates, the last one is returned by
        this function.
        """
        if not certificates:
            raise ValueError("chain must have at least one certificate")
        if now is None:
            now = int(time.time() * 1000)

        def _check_cert_validity(cert):
            if cert.payload["exp"] < now:
                raise ExpiredSignatureError("expired certificate in chain")

        # Here, two different use cases are being handled.
        # if there is only one bundled certificate, then send the data with
        # the hostname. If there are more than one certificate, checks need
        # to be done directly using the certificate data from the bundled
        # certificates, so all the information is passed along

        issuer = certificates[0].payload["iss"]
        current_key = None
        for cert in certificates:
            _check_cert_validity(cert)
            if not self.check_token_signature(cert, current_key,
                                              hostname=issuer):
                raise InvalidSignatureError("bad signature in chain")
            current_key = cert.payload["public-key"]
        return cert

    def check_token_signature(self, data, cert=None, hostname=None):
        """Check the signature of the given data according the the given
        certificate or hostname.

        In any cases, the verification is done in the PowerHose worker,
        using the hostname and not the given data enclosed in the certificate.

        This means that the payload of the given certificate should contain
        an "iss" key with the hostname of the certificate issuer.

        :param data: the data the check the validity of
        :param cert: the certificate to use for the verification
        :param hostname: the hostname to get the certificate from
        :param key: if provided, this key will be used to check the signature.
        """
        if hostname is None and cert is None:
            raise ValueError("You should specify either cert or hostname")

        if cert:
            key = json.dumps(cert.payload['public-key'])
            return self.runner.check_signature_with_cert(
                cert=key,
                signed_data=data.signed_data,
                signature=data.signature,
                algorithm=data.algorithm
            )

        return self.runner.check_signature(hostname=hostname,
                                           signed_data=data.signed_data,
                                           signature=data.signature,
                                           algorithm=data.algorithm)

    def is_trusted_issuer(self, hostname, issuer):
        """Check whether the issuer is trusted for a given hostname.

        This check is sent to the PowerHose worker because it may need to
        access cached support-document data.

        :param hostname: the hostname for which a key has been issued
        :param issuer: the hostname that issued the key in question
        """
        secondaries = json.dumps(self.trusted_secondaries)
        return self.runner.is_trusted_issuer(hostname=hostname,
                                             issuer=issuer,
                                             trusted_secondaries=secondaries)
