from collections import defaultdict

from pyramid.threadlocal import get_current_registry
from zope.interface import implements
from tokenserver.assignment import INodeAssignment

from mozsvc.exceptions import BackendError

# very basic in memory implementation of user to node assignation. This should
# be done in a persistant way instead.
_USERS_UIDS = defaultdict(dict)
_UID = 0


class DefaultNodeAssignmentBackend(object):
    """Dead simple NodeAssignment backend always returning the same service
    entry. This is useful in the case we don't need to deal with multiple
    services (e.g if someone wants to setup his own tokenserver always using
    the same node)
    """
    implements(INodeAssignment)

    def __init__(self, service_entry=None, **kw):
        self._service_entry = service_entry

    @property
    def service_entry(self):
        """Implement this as a property to have the context when looking for
        the value of the setting"""
        if self._service_entry is None:
            settings = get_current_registry().settings
            self._service_entry = settings.get('tokenserver.service_entry')
        return self._service_entry

    def get_node(self, email, service, version):
        uid = _USERS_UIDS.get((service, version), {}).get(email, None)
        return uid, self.service_entry

    def allocate_node(self, email, service, version):
        if self.get_node(email, service, version) != (None, self.service_entry):
            raise BackendError("Node already assigned")

        global _UID
        uid = _UID
        _UID += 1
        _USERS_UIDS[service, version][email] = uid

        return uid, self.service_entry
