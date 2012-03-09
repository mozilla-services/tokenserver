# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import json

from cornice import Service
from vep.errors import Error as BrowserIDError

from tokenserver.util import JsonError
from tokenserver.verifiers import get_verifier

# A GET on / returns the discovery API

discovery = Service(name='discovery', path='/')
token = Service(name='token', path='/1.0/{application}/{version}')


@discovery.get()
def _discovery(request):
    discovery = os.path.join(os.path.dirname(__file__), 'discovery.json')

    with open(discovery) as f:
        return json.loads(f.read())


# validators
def valid_assertion(request):
    """Validate that the assertion given in the request is correct.

    If not, add errors in the response so that the client can know what
    happened.
    """
    def _raise_unauthorized():
        raise JsonError(401, description='Unauthorized')

    token = request.headers.get('Authorization')
    if token is None:
        _raise_unauthorized()

    token = token.split()
    if len(token) != 2:
        _raise_unauthorized()

    name, assertion = token
    if name.lower() != 'browser-id':
        resp = JsonError(401, description='Unsupported')
        resp.www_authenticate = ('Browser-ID', {})
        raise resp

    try:
        verifier = get_verifier()
        verifier.verify(assertion)
    except BrowserIDError:
        _raise_unauthorized()

    # everything sounds good, add the assertion to the list of validated fields
    # and continue

    request.validated['assertion'] = assertion


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


@token.get(validators=(valid_app, valid_assertion))
def return_token(request):

    # XXX here, build the token
    assertion = request.validated['assertion']
    application = request.validated['application']
    version = request.validated['version']
    #email = request.validated['email']
    secrets = request.registry.settings['tokenserver.secrets_file']

    return {'service_entry': 'http://example.com'}
