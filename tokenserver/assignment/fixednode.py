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
        self._metadata = defaultdict(dict)
        self._flag = defaultdict(bool)

    @property
    def service_entry(self):
        """Implement this as a property to have the context when looking for
        the value of the setting"""
        if self._service_entry is None:
            settings = get_current_registry().settings
            self._service_entry = settings.get('tokenserver.service_entry')
        return self._service_entry

    def get_node(self, email, service):
        uid = _USERS_UIDS.get(service, {}).get(email, None)
        if not self._flag[service]:
            urls = self.get_metadata(service, needs_acceptance=True)
        else:
            urls = None

        return uid, self.service_entry, urls

    def allocate_node(self, email, service):
        status = self.get_node(email, service)
        if status[0] is not None:
            raise BackendError("Node already assigned")

        global _UID
        uid = _UID
        _UID += 1
        _USERS_UIDS[service][email] = uid

        return uid, self.service_entry

    def set_metadata(self, service, name, value, needs_acceptance=False):
        self._metadata[service][name] = value, needs_acceptance

    def get_metadata(self, service, name=None, needs_acceptance=None):
        metadata = []

        if name is None:
            items = self._metadata[service].items()
            for name, (value, _needs_acceptance) in items:
                if needs_acceptance is not None:
                    if needs_acceptance == _needs_acceptance:
                        metadata.append((name, value, _needs_acceptance))
                else:
                    metadata.append((name, value, _needs_acceptance))
        else:
            value, _needs_acceptance = self._metadata[service][name]
            if needs_acceptance is not None:
                if needs_acceptance == _needs_acceptance:
                    metadata.append((name, value, _needs_acceptance))
            else:
                metadata.append((name, value, _needs_acceptance))

        return metadata

    def set_accepted_conditions_flag(self, service, value, email=None):
        self._flag[service] = value
