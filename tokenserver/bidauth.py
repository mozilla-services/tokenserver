import binascii

from zope.interface import implements

from paste.httpheaders import AUTHORIZATION
from paste.httpheaders import WWW_AUTHENTICATE

from pyramid.interfaces import IAuthenticationPolicy
from pyramid.security import Everyone
from pyramid.security import Authenticated

import vep

_URL = 'http://tokenserver.services.mozilla.com'


class BrowserIDPolicy(object):
    """ A :app:`Pyramid` :term:`authentication policy` which
    obtains data from basic authentication headers.
    """
    implements(IAuthenticationPolicy)

    def __init__(self, verify_type):
        if verify_type not in ('local', 'remote', 'dummy'):
            raise ValueError(verify_type)
        self.verify_type = verify_type
        if verify_type == 'local':
            self.verifier = vep.verify_local
        elif verify_type == 'dummy':
            self.verifier = vep.verify_dummy
        else:
            self.verifier = vep.verify

    def verify(self, request):
        authorization = AUTHORIZATION(request.environ)
        try:
            authmeth, assertion = authorization.split(' ', 1)
        except ValueError: # not enough values to unpack
            return None

        if authmeth.lower() == 'browser-id':
            return self.verifier(assertion, _URL)

        return None

    def authenticated_userid(self, request):
        credentials = self.verify(request)
        if credentials is None:
            return None
        return credentials['email']

    def effective_principals(self, request):
        effective_principals = [Everyone]
        credentials = self.verify(request)
        if credentials is None:
            return effective_principals
        email = credentials['email']
        effective_principals.append(Authenticated)
        effective_principals.append(email)
        return effective_principals

    def unauthenticated_userid(self, request):
        creds = self._get_credentials(request)
        if creds is not None:
            return creds['email']
        return None

    def remember(self, request, principal, **kw):
        return []

    def forget(self, request):
        head = WWW_AUTHENTICATE.tuples('Basic realm="%s"' % self.realm)
        return head
