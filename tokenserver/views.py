# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import time
import os
import json
import re

from mozsvc.metrics import MetricsService

import tokenlib

from tokenserver.util import json_error
from tokenserver.verifiers import get_verifier
from tokenserver.assignment import INodeAssignment

from browserid.errors import Error as BrowserIDError
from tokenserver.crypto.master import ClientCatchedError

# A GET on / returns the discovery API

discovery = MetricsService(name='discovery', path='/')
token = MetricsService(name='token', path='/1.0/{application}/{version}')

DEFAULT_TOKEN_DURATION = 5 * 60


def get_service_name(application, version):
    return "%s-%s" % (application, version)


@discovery.get()
def _discovery(request):
    """Returns a JSON file containing the list of services supported byt the
    server"""

    discovery = os.path.join(os.path.dirname(__file__), 'discovery.json')

    with open(discovery) as f:
        return json.loads(f.read())


# validators
def valid_assertion(request):
    """Validate that the assertion given in the request is correct.

    If not, add errors in the response so that the client can know what
    happened.
    """
    metlog = request.registry['metlog']

    def _unauthorized():
        return json_error(401, description='Unauthorized')

    token = request.headers.get('Authorization')
    if token is None:
        raise _unauthorized()

    token = token.split()
    if len(token) != 2:
        raise _unauthorized()

    name, assertion = token
    if name.lower() != 'browser-id':
        resp = json_error(401, description='Unsupported')
        resp.www_authenticate = ('Browser-ID', {})
        raise resp

    def _handle_exception(error_type):
        # convert CamelCase to camel_case
        error_type = re.sub('(?<=.)([A-Z])', r'_\1', error_type).lower()

        metlog.incr('token.assertion.verify_failure')
        metlog.incr('token.assertion.%s' % error_type)
        if error_type == "connection_error":
            raise json_error(503, description="Resource is not available")
        else:
            raise _unauthorized()

    try:
        verifier = get_verifier()
        assertion = verifier.verify(assertion)
    except ClientCatchedError as e:
        _handle_exception(e.error_type)
    except BrowserIDError as e:
        _handle_exception(e.__class__.__name__)

    # everything sounds good, add the assertion to the list of validated fields
    # and continue
    metlog.incr('token.assertion.verify_success')
    request.validated['assertion'] = assertion


def valid_app(request):
    """Checks that the given application is one of the compatible ones.

    If it's not the case, a 404 is issued with the appropriate information.
    """
    supported = request.registry.settings['tokenserver.applications']
    application = request.matchdict.get('application')
    version = request.matchdict.get('version')

    if application not in supported:
        raise json_error(404, location='url', name='application',
                        description='Unsupported application')
    else:
        request.validated['application'] = application

    supported_versions = supported[application]

    if version not in supported_versions:
        raise json_error(404, location='url', name=version,
                        description='Unsupported application version')
    else:
        request.validated['version'] = version
        accepted = (request.headers.get('X-Conditions-Accepted', None)
                    is not None)
        request.validated['x-conditions-accepted'] = accepted


def pattern_exists(request):
    """Checks that the given service do have an associated pattern in the db or
    in the configuration file.

    If not, raises a 503 error.
    """
    application = request.validated['application']
    version = request.validated['version']
    defined_patterns = request.registry['endpoints_patterns']
    service = get_service_name(application, version)
    try:
        pattern = defined_patterns[service]
    except KeyError:
        raise json_error(503,
                description="The api_endpoint pattern for %r is not known"
                % service)

    request.validated['pattern'] = pattern


@token.get(validators=(valid_app, valid_assertion, pattern_exists))
def return_token(request):
    """This service does the following process:

    - validates the Browser-ID assertion provided on the Authorization header
    - allocates when necessary a node to the user for the required service
    - deals with the X-Conditions-Accepted header
    - returns a JSON mapping containing the following values:

        - **id** -- a signed authorization token, containing the
          user's id for hthe application and the node.
        - **secret** -- a secret derived from the shared secret
        - **uid** -- the user id for this servic
        - **api_endpoint** -- the root URL for the user for the service.
    """
    # at this stage, we are sure that the assertion, application and version
    # number were valid, so let's build the authentication token and return it.
    backend = request.registry.getUtility(INodeAssignment)
    email = request.validated['assertion']['email']
    application = request.validated['application']
    version = request.validated['version']
    pattern = request.validated['pattern']
    service = get_service_name(application, version)
    accepted = request.validated['x-conditions-accepted']

    # get the node or allocate one if none is already set
    uid, node, to_accept = backend.get_node(email, service)
    if to_accept is not None:
        # the backend sent a tos url, meaning the user needs to
        # sign it, we want to compare both tos and raise a 403
        # if they are not equal
        if not accepted:
            to_accept = dict([(name, value) for name, value, __ in to_accept])
            raise json_error(403, location='header',
                            description='Need to accept conditions',
                            name='X-Conditions-Accepted',
                            condition_urls=to_accept)
    # at this point, either the tos were signed or the service does not
    # have any ToS
    if node is None or uid is None:
        metlog = request.registry['metlog']
        start = time.time()
        try:
            uid, node = backend.allocate_node(email, service)
        finally:
            duration = time.time() - start
            metlog.timer_send("token.sql.allocate_node", duration)

    secrets = request.registry.settings['tokenserver.secrets_file']
    node_secrets = secrets.get(node)
    if not node_secrets:
        raise Exception("The specified node does not have any shared secret")
    secret = node_secrets[-1]  # the last one is the most recent one

    token_duration = request.registry.settings.get(
            'tokenserver.token_duration', DEFAULT_TOKEN_DURATION)

    token = tokenlib.make_token({'uid': uid, 'service_entry': node},
                                timeout=token_duration, secret=secret)
    secret = tokenlib.get_derived_secret(token, secret=secret)

    api_endpoint = pattern.format(uid=uid, service=service, node=node)

    return {'id': token, 'key': secret, 'uid': uid,
            'api_endpoint': api_endpoint, 'duration': token_duration,
            'hashalg': tokenlib.DEFAULT_HASHMOD}
