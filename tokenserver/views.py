# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import time
import os
import json
import re
import contextlib

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


def _unauthorized(status_message='error', **kw):
    kw.setdefault('description', 'Unauthorized')
    return json_error(401, status_message, **kw)


# validators
def valid_assertion(request):
    """Validate that the assertion given in the request is correct.

    If not, add errors in the response so that the client can know what
    happened.
    """
    metlog = request.registry['metlog']

    token = request.headers.get('Authorization')
    if token is None:
        raise _unauthorized()

    token = token.split()
    if len(token) != 2:
        raise _unauthorized()

    name, assertion = token
    if name.lower() != 'browserid':
        resp = _unauthorized(description='Unsupported')
        resp.www_authenticate = ('BrowserID', {})
        raise resp

    def _handle_exception(error_type):
        # convert CamelCase to camel_case
        error_type = re.sub('(?<=.)([A-Z])', r'_\1', error_type).lower()

        metlog.incr('token.assertion.verify_failure')
        metlog.incr('token.assertion.%s' % error_type)
        if error_type == "connection_error":
            raise json_error(503, description="Resource is not available")
        if error_type == "expired_signature_error":
            raise _unauthorized("invalid-timestamp")
        else:
            raise _unauthorized("invalid-credentials")

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


def valid_client_state(request):
    """Checks for and validates the X-Client-State header."""
    client_state = request.headers.get('X-Client-State', '')
    if client_state:
        if not re.match("[a-zA-Z0-9._-]{1,32}", client_state):
            raise json_error(400, location='header', name='X-Client-State',
                             description='Invalid client state value')
    request.validated['client-state'] = client_state


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


VALIDATORS = (valid_app, valid_client_state, valid_assertion, pattern_exists)

@token.get(validators=VALIDATORS)
def return_token(request):
    """This service does the following process:

    - validates the BrowserID assertion provided on the Authorization header
    - allocates when necessary a node to the user for the required service
    - checks generation numbers and x-client-state header
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
    generation = request.validated['assertion'].get('generation', 0)
    application = request.validated['application']
    version = request.validated['version']
    pattern = request.validated['pattern']
    service = get_service_name(application, version)
    client_state = request.validated['client-state']

    with time_backend_operation(request, 'tokenserver.sql.get_user'):
        user = backend.get_user(service, email)
    if not user:
        with time_backend_operation(request, 'tokenserver.sql.create_user'):
            user = backend.create_user(service, email, generation, client_state)

    # Update if this client is ahead of previously-seen clients.
    updates = {}
    if generation > user['generation']:
        updates['generation'] = generation
    if client_state != user['client_state']:
        if client_state not in user['old_client_states']:
            updates['client_state'] = client_state
    if updates:
        with time_backend_operation(request, 'tokenserver.sql.update_user'):
            backend.update_user(service, user, **updates)

    # Error out if this client is behind some previously-seen client.
    # This is done after the updates because some other, even more up-to-date
    # client may have raced with a concurrent update.
    if user['generation'] > generation:
        raise _unauthorized("invalid-generation")
    if client_state in user['old_client_states']:
        raise _unauthorized("invalid-client-state")

    secrets = request.registry.settings['tokenserver.secrets_file']
    node_secrets = secrets.get(user['node'])
    if not node_secrets:
        raise Exception("The specified node does not have any shared secret")
    secret = node_secrets[-1]  # the last one is the most recent one

    token_duration = request.registry.settings.get(
            'tokenserver.token_duration', DEFAULT_TOKEN_DURATION)

    token = tokenlib.make_token({'uid': user['uid'], 'node': user['node']},
                                timeout=token_duration, secret=secret)
    secret = tokenlib.get_derived_secret(token, secret=secret)

    endpoint = pattern.format(uid=user['uid'], service=service, node=user['node'])

    return {'id': token, 'key': secret, 'uid': user['uid'],
            'api_endpoint': endpoint, 'duration': token_duration,
            'hashalg': tokenlib.DEFAULT_HASHMOD}


@contextlib.contextmanager
def time_backend_operation(request, name):
    metlog = request.registry['metlog']
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        metlog.timer_send(name, duration)
