import hashlib

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
        self._test_settings = {}  # unit test specific overrides
        self._settings = kw or {}

    @property
    def settings(self):
        # Normalize the various settings by picking out the
        # `tokenserver.` settings from the pyramid settings
        # registry, remove the namespace prefix so that they
        # match the values that should be passed in as *kw
        # to the __init__()
        settings = dict(
           map(lambda (k, v): (
               k.replace('tokenserver.', ''), v),
               filter(lambda e: e[0].startswith('tokenserver.'),
                      (get_current_registry().settings or {}).items()))
        ) or self._settings
        settings.update(self._test_settings)
        return settings

    @property
    def service_entry(self):
        """Implement this as a property to have the context when looking for
        the value of the setting"""
        if self._service_entry is None:
            self._service_entry = self.settings.get('service_entry')
        return self._service_entry

    def clear(self):
        self._users.clear()
        self._next_uid = 1

    def get_user(self, service, email):
        try:
            return self._users[(service, email)].copy()
        except KeyError:
            return None

    def allocate_to_spanner(self, email):
        """use a simple, reproducable hashing mechanism to determine if
        a user should be provisioned to spanner. Does not need to be
        secure, just a selectable percentage."""
        return ord(hashlib.sha1(email.encode()).digest()[0]) < (
            256 * (self.settings.get(
                    'migrate_new_user_percentage', 0) * .01))

    def allocate_user(self, service, email, generation=0, client_state='',
                      keys_changed_at=0, node=None):
        if (service, email) in self._users:
            raise BackendError('user already exists: ' + email)
        if node is not None and node != self.service_entry:
            raise ValueError("unknown node: %s" % (node,))
        if self.allocate_to_spanner(email):
            service_entry = self.settings.get('spanner_entry')
        else:
            service_entry = self.service_entry
        user = {
            'email': email,
            'uid': self._next_uid,
            'node': service_entry,
            'generation': generation,
            'keys_changed_at': keys_changed_at,
            'client_state': client_state,
            'old_client_states': {},
            'first_seen_at': get_timestamp(),
        }
        self._users[(service, email)] = user
        self._next_uid += 1
        return user.copy()

    def update_user(self, service, user, generation=None, client_state=None,
                    keys_changed_at=None, node=None):
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
        self._users[(service, user['email'])].update(user)
