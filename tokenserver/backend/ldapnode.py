from repoze.who.plugins.vepauth.tokenmanager import SignedTokenManager
from pyramid.threadlocal import get_current_registry

from cornice.util import json_error
from zope.interface import implements
from cornice.errors import Errors
from tokenserver.backend import INodeAssignment


class LDAPNodeAssignmentBackend(INodeAssignment):
    """Implements a node assignment backend.

    Uses a simple ldap calls and relying on the APIs for reg/sreg otherwise
    """
    implements(IAppSyncDatabase)

    def __init__(self, ldap, sreg, snode, cache):
        self.ldap = ldap
        self.sreg = sreg
        self.snode = snode
        self.cache = cache

    def get_node(self, email, service):
        """Returns the node from the given email and user, calling LDAP
        directly.
        """
        # make a call to ldap
        # if the user does not exist, return the associated node
        raise NotImplementedError()

    def create_node(self, email, service):
        """Assign the given set of email and service to a node"""
        # make a call to the API via REST
        # adds the created mapping to the cache
        # and return the assigned Node
        # in case it fails, catch the exception and return None
        raise NotImplementedError()
