# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import json

from cornice import Service
from browserid.errors import Error as BrowserIDError

from tokenlib import make_token, get_token_secret

from tokenserver.util import JsonError
from tokenserver.verifiers import get_verifier
from tokenserver.assignment import INodeAssignment

# A GET on / returns the discovery API

discovery = Service(name='discovery', path='/')
token = Service(name='token', path='/1.0/{application}/{version}')


def get_service_name(application, version):
    return "%s-%s" % (application, version)


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
        assertion = verifier.verify(assertion)
    except BrowserIDError:
        _raise_unauthorized()

    # everything sounds good, add the assertion to the list of validated fields
    # and continue
    request.validated['assertion'] = assertion


def valid_app(request):
    """Checks that the given application is one of the compatible ones.

    If it's not the case, a 404 is issued with the appropriate information.
    """
    supported = request.registry.settings['tokenserver.applications']
    application = request.matchdict.get('application')
    version = request.matchdict.get('version')

    if application not in supported:
        raise JsonError(404, location='url', name='application',
                        description='Unsupported application')
    else:
        request.validated['application'] = application

    supported_versions = supported[application]

    if version not in supported_versions:
        raise JsonError(404, location='url', name=version,
                        description='Unsupported application version')
    else:
        request.validated['version'] = version


def pattern_exists(request):
    """Checks that the given service do have an associated pattern in the db or
    in the configuration file.

    If not, raises a 500 error.
    """
    application = request.validated['application']
    version = request.validated['version']
    defined_patterns = request.registry['endpoints_patterns']
    service = get_service_name(application, version)
    try:
        pattern = defined_patterns[service]
    except KeyError:
        raise JsonError(500,
                description="The api_endpoint pattern for %r is not known"
                % service)

    request.validated['pattern'] = pattern


@token.get(validators=(valid_app, valid_assertion, pattern_exists))
def return_token(request):
    # at this stage, we are sure that the assertion, application and version
    # number were valid, so let's build the authentication token and return it.

    backend = request.registry.getUtility(INodeAssignment)
    email = request.validated['assertion']['email']
    application = request.validated['application']
    version = request.validated['version']
    pattern = request.validated['pattern']
    service = get_service_name(application, version)

    # get the node or allocate one if none is already set
    uid, node = backend.get_node(email, service)
    if node is None or uid is None:
        uid, node = backend.allocate_node(email, service)

    secrets = request.registry.settings['tokenserver.secrets_file']
    node_secrets = secrets.get(node)
    if not node_secrets:
        raise Exception("The specified node does not have any shared secret")
    secret = node_secrets[-1]  # the last one is the most recent one

    token = make_token({'uid': uid, 'service_entry': node}, secret=secret)
    # XXX needs to be renamed as 'get_derived_secret' because
    # it's not clear here it's a derived
    secret = get_token_secret(token, secret=secret)

    api_endpoint = pattern.format(uid=uid, service=service, node=node)

    # FIXME add the algo used to generate the token
    return {'id': token, 'key': secret, 'uid': uid,
            'api_endpoint': api_endpoint}
