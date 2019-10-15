
from pyramid.threadlocal import get_current_registry
from zope.interface import implements

from tokenserver.assignment import INodeAssignment
from tokenserver.util import get_timestamp

from mozsvc.exceptions import BackendError


class MemoryNodeAssignmentBackend(object):
    """Simple in-memory INodeAssignment backend.

    This is useful for testing purposes and probably not much else.
    """
    implements(INodeAssignment)

    def __init__(self, service_entry=None, **kw):
        self._service_entry = service_entry
        self._users = {}
        self._next_uid = 1

    @property
    def service_entry(self):
        """Implement this as a property to have the context when looking for
        the value of the setting"""
        if self._service_entry is None:
            settings = get_current_registry().settings
            self._service_entry = settings.get('tokenserver.service_entry')
        return self._service_entry

    def clear(self):
        self._users.clear()
        self._next_uid = 1

    def get_user(self, service, email):
        return self._users.get((service, email), None)

    def allocate_user(self, service, email, generation=0, client_state='',
                      node=None, keys_changed_at=None):
        if (service, email) in self._users:
            raise BackendError('user already exists: ' + email)
        if node is not None and node != self.service_entry:
            raise ValueError("unknown node: %s" % (node,))
        user = {
            'email': email,
            'uid': self._next_uid,
            'node': self.service_entry,
            'generation': generation,
            'keys_changed_at': keys_changed_at,
            'client_state': client_state,
            'old_client_states': {},
            'first_seen_at': get_timestamp()
        }
        self._users[(service, email)] = user
        self._next_uid += 1
        return user

    def update_user(self, service, user, generation=None, client_state=None,
                    node=None, keys_changed_at=None):
        if (service, user['email']) not in self._users:
            raise BackendError('unknown user: ' + user['email'])
        if node is not None and node != self.service_entry:
            raise ValueError("unknown node: %s" % (node,))
        if generation is not None:
            user['generation'] = generation
        if keys_changed_at is not None:
            user['keys_changed_at'] = keys_changed_at
        if client_state is not None:
            user['old_client_states'][user['client_state']] = True
            user['client_state'] = client_state
            user['uid'] = self._next_uid
            self._next_uid += 1
