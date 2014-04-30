import json

from pyramid.threadlocal import get_current_registry
from zope.interface import implements, Interface

import socket
import requests

from browserid.verifiers.local import LocalVerifier as LocalVerifier_
from browserid.errors import (InvalidSignatureError, ExpiredSignatureError,
                              ConnectionError, AudienceMismatchError,
                              InvalidIssuerError)


def get_verifier(registry=None):
    """returns the registered verifier, building it if necessary."""
    if registry is None:
        registry = get_current_registry()
    return registry.getUtility(IBrowserIdVerifier)


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
