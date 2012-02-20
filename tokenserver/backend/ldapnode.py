from zope.interface import implements
from tokenserver.backend import INodeAssignment

from ldappool import ConnectionManager
import ldap

from tokenserver import logger
from tokenserver.util import (SRegBackend, SNodeBackend, decode_ldap_uri,
                              hash_email)


class LDAPNodeAssignmentBackend(object):
    """Implements a node assignment backend.

    Uses a simple ldap calls and relying on the APIs for reg/sreg otherwise
    """
    implements(INodeAssignment)

    def __init__(self, ldap, sreg, snode, cache):
        self.sreg_uri = sreg
        self.snode_uri = snode
        self.ldap_uri = ldap
        self.snode_path = "/1.0/"
        self.sreg_path = "/1.0/"

        self.cache = cache
        self._pool = None
        self._snode = None
        self._sreg = None

    @property
    def pool(self):
        # This is a property to allow lazy loading.
        if self._pool is None:
            ldap_uri, bind_user, bind_password = decode_ldap_uri(self.ldap_uri)
            self._pool = ConnectionManager(ldap_uri, bind_user, bind_password)
        return self._pool

    @property
    def snode(self):
        # This is a property to allow lazy loading.
        if self._snode is None:
            self._snode = SNodeBackend(self.snode_uri, self.snode_path)
        return self._snode

    @property
    def sreg(self):
        # This is a property to allow lazy loading.
        if self._sreg is None:
            self._sreg = SRegBackend(self.sreg_uri, self.sreg_path)
        return self._sreg

    def get_node(self, email, service):
        """Returns the node from the given email and user, calling LDAP
        directly.

        If the user does not exist, return None.

        This implementation uses the sync1 ldap and thus doesn't know about
        having different services. The APIs intend to support having multiple
        (email, service) associations, but that's not the case just now.

        :param email: the email of the user to look the node for
        :param service: the service to look for
        """
        # make a call to ldap
        with self.pool.connection() as conn:
            try:
                res = conn.search_st('ou=users,dc=mozilla',
                                     ldap.SCOPE_BASE,
                                     filterstr='(mail=%s)' % email,
                                     attrlist=['primaryNode'])
                if not res:
                    return None, None

                data = res[0][1]
                username = hash_email(email)

                if 'primaryNode' not in data:
                    return None, username
                return data['primaryNode'], username

            except (ldap.TIMEOUT, ldap.SERVER_DOWN, ldap.OTHER) as e:
                logger.critical(e)
                raise e

    def create_node(self, email, service):
        """Assign the given set of email and service to a node"""
        node, username = self.get_node(email, service)

        if username is None:
            node = self.sreg.create_user(email)
        elif node is None:
            node = self.snode.allocate_user(email)
        return node
