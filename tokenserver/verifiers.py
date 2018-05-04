import json
import warnings

from pyramid.threadlocal import get_current_registry
from zope.interface import implements, Interface
from zope.interface.interfaces import ComponentLookupError # noqa; for re-export only

import socket
import requests
import urlparse

import browserid.verifiers.local
from browserid.errors import (InvalidSignatureError, ExpiredSignatureError,
                              ConnectionError, AudienceMismatchError,
                              InvalidIssuerError)
from browserid.supportdoc import SupportDocumentManager

import fxa.oauth
import fxa.errors
import fxa.constants


DEFAULT_OAUTH_SCOPE = 'https://identity.mozilla.com/apps/oldsync'


def get_browserid_verifier(registry=None):
    """Returns the registered browserid verifier.

    If no browserid verifier is registered, raises ComponentLookupError.
    """
    if registry is None:
        registry = get_current_registry()
    return registry.getUtility(IBrowserIdVerifier)


def get_oauth_verifier(registry=None):
    """Returns the registered oauth verifier.

    If no oauth verifier is registered, raises ComponentLookupError.
    """
    if registry is None:
        registry = get_current_registry()
    return registry.getUtility(IOAuthVerifier)


# This is to simplify the registering of the implementations using pyramid
# registry.
class IBrowserIdVerifier(Interface):
    pass


class IOAuthVerifier(Interface):
    pass


# The default verifier from browserid
class LocalBrowserIdVerifier(browserid.verifiers.local.LocalVerifier):
    implements(IBrowserIdVerifier)

    def __init__(self, trusted_issuers=None, allowed_issuers=None, **kwargs):
        """LocalVerifier constructor, with the following extra config options:

        :param ssl_certificate: The path to an optional ssl certificate to
            use when doing SSL requests with the BrowserID server.
            Set to True (the default) to use default certificate authorities.
            Set to False to disable SSL verification.
        """
        if isinstance(trusted_issuers, basestring):
            trusted_issuers = trusted_issuers.split()
        self.trusted_issuers = trusted_issuers
        if trusted_issuers is not None:
            kwargs["trusted_secondaries"] = trusted_issuers
        if isinstance(allowed_issuers, basestring):
            allowed_issuers = allowed_issuers.split()
        self.allowed_issuers = allowed_issuers
        if "ssl_certificate" in kwargs:
            verify = kwargs["ssl_certificate"]
            kwargs.pop("ssl_certificate")
            if not verify:
                self._emit_warning()
        else:
            verify = None
        kwargs["supportdocs"] = SupportDocumentManager(verify=verify)
        # Disable warning about evolving data formats, it's out of date.
        kwargs.setdefault("warning", False)
        super(LocalBrowserIdVerifier, self).__init__(**kwargs)

    def _emit_warning():
        """Emit a scary warning to discourage unverified SSL access."""
        msg = "browserid.ssl_certificate=False disables server's certificate"\
              "validation and poses a security risk. You should pass the path"\
              "to your self-signed certificate(s) instead. "\
              "For more information on the ssl_certificate parameter, see "\
              "http://docs.python-requests.org/en/latest/user/advanced/"\
              "#ssl-cert-verification"
        warnings.warn(msg, RuntimeWarning, stacklevel=2)

    def verify(self, assertion, audience=None):
        data = super(LocalBrowserIdVerifier, self).verify(assertion, audience)
        if self.allowed_issuers is not None:
            issuer = data.get('issuer')
            if issuer not in self.allowed_issuers:
                raise InvalidIssuerError("Issuer not allowed: %s" % (issuer,))
        return data


# A verifier that posts to a remote verifier service.
# The RemoteVerifier implementation from PyBrowserID does its own parsing
# of the assertion, and hasn't been updated for the new BrowserID formats.
# Rather than blocking on that work, we use a simple work-alike that doesn't
# do any local inspection of the assertion.
class RemoteBrowserIdVerifier(object):
    implements(IBrowserIdVerifier)

    def __init__(self, audiences=None, trusted_issuers=None,
                 allowed_issuers=None, verifier_url=None, timeout=None):
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
        if timeout is None:
            timeout = 30
        self.timeout = timeout
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
                                         headers=headers,
                                         timeout=self.timeout)
        except (socket.error, requests.RequestException), e:
            msg = "Failed to POST %s. Reason: %s" % (self.verifier_url, str(e))
            raise ConnectionError(msg)

        if response.status_code != 200:
            raise ConnectionError('server returned invalid response code')
        try:
            data = json.loads(response.text)
        except ValueError:
            raise ConnectionError("server returned invalid response body")

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


class RemoteOAuthVerifier(object):
    """A Verifier for FxA OAuth tokens that posts to a verifiaction service.

    This verifier uses the remote FxA OAuth verification service to accept
    OAuth tokens, and translates the returned data into something that
    approximates the information provided by BrowserID.

    In order to meet tokenserver's expectation that users are identified
    with an email address, it combines the FxA uid with the hostname of
    the corresponding FxA BrowserID issuer.  For non-standard FxA hosting
    setups this might require it to dynamically discover the BrowserID
    issuer by querying the OAuth verifier's configuration.
    """
    implements(IOAuthVerifier)

    def __init__(self, server_url=None, default_issuer=None, timeout=30,
                 scope=DEFAULT_OAUTH_SCOPE):
        if not scope:
            raise ValueError('Expected a non-empty "scope" argument')
        self._client = fxa.oauth.Client(server_url=server_url)
        self._client.timeout = timeout
        if default_issuer is None:
            # This server_url will have been normalized to end in /v1.
            server_url = self._client.server_url
            # Try to find the auth-server that matches the given oauth-server.
            # For well-known servers this avoids discovering it dynamically.
            for urls in fxa.constants.ENVIRONMENT_URLS.itervalues():
                if urls['oauth'] == server_url:
                    auth_url = urls['authentication']
                    default_issuer = urlparse.urlparse(auth_url).netloc
                    break
            else:
                # For non-standard hosting setups, look it up dynamically.
                r = requests.get(server_url[:-3] + '/config')
                r.raise_for_status()
                try:
                    default_issuer = r.json()['browserid']['issuer']
                except KeyError:
                    pass
        self.default_issuer = default_issuer
        self.scope = scope

    @property
    def server_url(self):
        return self._client.server_url

    @property
    def timeout(self):
        return self._client.timeout

    def verify(self, token):
        try:
            userinfo = self._client.verify_token(token, self.scope)
        except (socket.error, requests.RequestException), e:
            msg = 'Verification request to %s failed; reason: %s'
            msg %= (self.server_url, str(e))
            raise ConnectionError(msg)
        issuer = userinfo.get('issuer', self.default_issuer)
        if not issuer or not isinstance(issuer, basestring):
            msg = 'Could not determine issuer from verifier response'
            raise fxa.errors.TrustError(msg)
        return {
          'email': userinfo['user'] + '@' + issuer,
          'idpClaims': {},
        }


# For backwards-compatibility with self-hosting setups
# which might be referencing these via their old names.
LocalVerifier = LocalBrowserIdVerifier
RemoteVerifier = RemoteBrowserIdVerifier
