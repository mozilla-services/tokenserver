from repoze.who.plugins.vepauth.tokenmanager import SignedTokenManager
from pyramid.threadlocal import get_current_registry

from cornice.util import json_error
from cornice.errors import Errors


class NodeTokenManager(SignedTokenManager):
    def __init__(self, node_assignment_backend=None, *args, **kw):
        self._backend = node_assignment_backend
        super(NodeTokenManager, self).__init__(*args, **kw)

    @property
    def node_assignment_backend(self):
        """Implement this as a property so we can have the context (and this
        the settings defined when requesting it"""

        if self._backend is None:
            # try to get it from the settings
            settings = get_current_registry().settings
            self._backend = settings.get(
                    'tokenserver.node_assignment_backend',
                    DefaultNodeAssignmentBackend())

            if not isinstance(self._backend, NodeAssignmentBackend):
                self._backend = load()

        return self._backend

    def make_token(self, request, data):
        email = data['email']
        service = request.matchdict['application']

        node = self.node_assignment_backend.get_node(email, service)
        if node is None:
            node = self.node_assignment_backend.create_node(email, service)

        extra = {'service_entry': node}
        token, secret, __ = super(NodeTokenManager, self)\
                                .make_token(request, data)

        return token, secret, extra

    def _validate_request(self, request, data):
        """Raise a cornice compatible error when the application is not
        one of the defined ones"""
        if ('application' in request.matchdict and self.applications and
                request.matchdict['application'] not in self.applications):
            errors = Errors()
            errors.add("uri", "application",
            "the application %s is not defined, please use one of %s" % (
                request.matchdict['application'],
                ", ".join(self.applications)))

            raise json_error(errors, 404)
