from repoze.who.plugins.vepauth.tokenmanager import SignedTokenManager
from pyramid.threadlocal import get_current_registry

from cornice.util import json_error
from cornice.errors import Errors

from tokenserver.backend import INodeAssignment


class NodeTokenManager(SignedTokenManager):
    def make_token(self, request, data):
        backend = get_current_registry().getUtility(INodeAssignment)
        email = data['email']
        service = request.matchdict['application']

        node = backend.get_node(email, service)
        if node is None:
            node = backend.create_node(email, service)

        extra = {'service_entry': node}
        token, secret, __ = super(NodeTokenManager, self)\
                                .make_token(request, data)

        return token, secret, extra

    def _validate_request(self, request, data):
        """Raise a cornice compatible error when the application is not
        one of the defined ones"""
        if self.applications == {}:
            return

        application = request.matchdict.get('application')
        version = request.matchdict.get('version')
        errors = Errors()

        if application not in self.applications:
            errors.add("uri", "application",
            "the application %r is not defined, please use one of %s" % (
                        application, ", ".join(self.applications.keys())))

        if version not in self.applications[application]:
            versions = self.applications[application]
            errors.add("uri", "version",
              ("the application %r is not defined for this version, please "
               "use one of %s") % (application, ", ".join(versions)))

        if len(errors) > 0:
            raise json_error(errors, 404)
