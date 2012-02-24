# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import json

from cornice import Service
from cornice.resource import resource, view

from tokenserver.util import JsonError

#
# Discovery page
#
discovery = Service(name='discovery', path='/')


@discovery.get()
def _discovery(request):
    discovery = os.path.join(os.path.dirname(__file__), 'discovery.json')

    with open(discovery) as f:
        return json.loads(f.read())


#
# token service
#
def valid_assertion(request):
    token = request.headers.get('Authorization')
    if token is None:
        raise JsonError(401, description='Unauthorized')
    token = token.split()
    if len(token) != 2:
        raise JsonError(401, description='Unauthorized')
    name, assertion = token
    if name.lower() != 'browser-id':
        resp = JsonError(401, description='Unsupported')
        resp.www_authenticate = ('Browser-ID', {})
        raise resp
    request.validated['assertion'] = assertion

    # XXX here call the tool that will validate the assertion
    # and set the email in request.validated['email']

def valid_app(request):
    supported = request.registry.settings['tokenserver.applications']
    application = request.matchdict.get('application')
    version = request.matchdict.get('version')

    if application not in supported:
        raise JsonError(404, location='url', name='application',
                        description='Unknown application')
    else:
        request.validated['application'] = application

    supported_versions = supported[application]

    if version not in supported_versions:
        raise JsonError(404, location='url', name=version,
                        description='Unknown application version')
    else:
        request.validated['version'] = version


@resource(path='/1.0/{application}/{version}')
class TokenService(object):
    def __init__(self, request):
        self.request = request


    @view(validators=(valid_app, valid_assertion))
    def get(self):
        request = self.request

        # XXX here, build the token
        assertion = request.validated['assertion']
        application = request.validated['application']
        version = request.validated['version']
        #email = request.validated['email']
        secrets = request.registry.settings['tokenserver.secrets_file']
        
        return {'service_entry': 'http://example.com'}
