from pyramid.threadlocal import get_current_registry
from zope.interface import implements
from tokenserver.backend import INodeAssignment


class DefaultNodeAssignmentBackend(object):
    """Dead simple NodeAssignment backend always returning the same service
    entry. This is useful in the case we don't need to deal with multiple
    services (e.g if someone wants to setup his own tokenserver always using
    the same node
    """
    implements(INodeAssignment)

    def __init__(self, service_entry=None, **kw):
        self._service_entry = service_entry

    @property
    def service_entry(self):
        """Implement this as a property to have the context when looking for
        the valiue of the setting"""
        if self._service_entry is None:
            settings = get_current_registry().settings
            self._service_entry = settings.get('tokenserver.service_entry')
        return self._service_entry

    def get_node(self, email, service):
        return self.service_entry

    def create_node(self, email, service):
        return self.service_entry
