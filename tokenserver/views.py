# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import re
import time
import logging

from cornice import Service
from mozsvc.metrics import metrics_timer

import tokenlib

from tokenserver.verifiers import get_verifier
from tokenserver.assignment import INodeAssignment
from tokenserver.util import json_error, fxa_metrics_hash

import browserid.errors


logger = logging.getLogger("tokenserver")

# A GET on / returns the discovery API

discovery = Service(name='discovery', path='/')
token = Service(name='token', path='/1.0/{application}/{version}')

DEFAULT_TOKEN_DURATION = 5 * 60


def get_service_name(application, version):
    return "%s-%s" % (application, version)


@discovery.get()
def _discovery(request):
    """Returns a JSON file listing the services supported by the server."""
    services = request.registry.settings['tokenserver.applications']
    discovery = {}
    discovery["services"] = services
    discovery["auth"] = request.url.rstrip("/")
    return discovery


def _unauthorized(status_message='error', **kw):
    kw.setdefault('description', 'Unauthorized')
    return json_error(401, status_message, **kw)


def _invalid_client_state(reason, **kw):
    kw.setdefault('location', 'header')
    kw.setdefault('name', 'X-Client-State')
    description = 'Unacceptable client-state value %s' % (reason,)
    kw.setdefault('description', description)
    return _unauthorized('invalid-client-state', **kw)


# validators
def valid_assertion(request):
    """Validate that the assertion given in the request is correct.

    If not, add errors in the response so that the client can know what
    happened.
    """
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

    try:
        verifier = get_verifier()
        with metrics_timer('tokenserver.assertion.verify', request):
            assertion = verifier.verify(assertion)
    except browserid.errors.Error as e:
        # Convert CamelCase to under_scores for reporting.
        error_type = e.__class__.__name__
        error_type = re.sub('(?<=.)([A-Z])', r'_\1', error_type).lower()
        request.metrics['token.assertion.verify_failure'] = 1
        request.metrics['token.assertion.%s' % error_type] = 1
        # Log a full traceback for errors that are not a simple
        # "your assertion was bad and we dont trust it".
        if not isinstance(e, browserid.errors.TrustError):
            logger.exception("Unexpected verification error")
        # Report an appropriate error code.
        if isinstance(e, browserid.errors.ConnectionError):
            raise json_error(503, description="Resource is not available")
        if isinstance(e, browserid.errors.ExpiredSignatureError):
            raise _unauthorized("invalid-timestamp")
        raise _unauthorized("invalid-credentials")

    # FxA sign-in confirmation introduced the notion of unverified tokens.
    # The default value is True to preserve backwards compatibility.
    try:
        tokenVerified = assertion['idpClaims']['fxa-tokenVerified']
    except KeyError:
        tokenVerified = True
    if not tokenVerified:
        raise _unauthorized("invalid-credentials")

    # everything sounds good, add the assertion to the list of validated fields
    # and continue
    request.metrics['token.assertion.verify_success'] = 1
    request.validated['assertion'] = assertion

    id_key = request.registry.settings.get("fxa.metrics_uid_secret_key")
    if id_key is None:
        id_key = 'insecure'
    email = assertion['email']
    fxa_uid_full = fxa_metrics_hash(email, id_key)
    # "legacy" key used by heka active_counts.lua
    request.metrics['uid'] = fxa_uid_full
    request.metrics['email'] = email

    # "new" keys use shorter values
    fxa_uid = fxa_uid_full[:32]
    request.validated['fxa_uid'] = fxa_uid
    request.metrics['fxa_uid'] = fxa_uid

    try:
        device = assertion['idpClaims']['fxa-deviceId']
        if device is None:
            device = 'none'
    except KeyError:
        device = 'none'
    device_id = fxa_metrics_hash(fxa_uid + device, id_key)[:32]
    request.validated['device_id'] = device_id
    request.metrics['device_id'] = device_id


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
        description = "The api_endpoint pattern for %r is not known" % service
        raise json_error(503, description=description)

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
    settings = request.registry.settings
    email = request.validated['assertion']['email']
    try:
        idp_claims = request.validated['assertion']['idpClaims']
        generation = idp_claims['fxa-generation']
        if not isinstance(generation, (int, long)):
            raise _unauthorized("invalid-generation")
    except KeyError:
        generation = 0
    application = request.validated['application']
    version = request.validated['version']
    pattern = request.validated['pattern']
    service = get_service_name(application, version)
    client_state = request.validated['client-state']

    with metrics_timer('tokenserver.backend.get_user', request):
        user = backend.get_user(service, email)
    if not user:
        allowed = settings.get('tokenserver.allow_new_users', True)
        if not allowed:
            raise _unauthorized('invalid-credentials')
        with metrics_timer('tokenserver.backend.allocate_user', request):
            user = backend.allocate_user(service, email, generation,
                                         client_state)

    # Update if this client is ahead of previously-seen clients.
    updates = {}
    if generation > user['generation']:
        updates['generation'] = generation
    if client_state != user['client_state']:
        # Don't revert from some-client-state to no-client-state.
        if not client_state:
            raise _invalid_client_state('empty string')
        # Don't revert to a previous client-state.
        if client_state in user['old_client_states']:
            raise _invalid_client_state('stale value')
        # If the IdP has been sending generation numbers, then
        # don't update client-state without a change in generation number.
        if user['generation'] > 0 and 'generation' not in updates:
            raise _invalid_client_state('new value with no generation change')
        updates['client_state'] = client_state
    if updates:
        with metrics_timer('tokenserver.backend.update_user', request):
            backend.update_user(service, user, **updates)

    # Error out if this client is behind some previously-seen client.
    # This is done after the updates because some other, even more up-to-date
    # client may have raced with a concurrent update.
    if user['generation'] > generation:
        raise _unauthorized("invalid-generation")

    secrets = settings['tokenserver.secrets']
    node_secrets = secrets.get(user['node'])
    if not node_secrets:
        raise Exception("The specified node does not have any shared secret")
    secret = node_secrets[-1]  # the last one is the most recent one

    # Clients can request a smaller token duration via an undocumented
    # query parameter, for testing purposes.
    token_duration = settings.get(
        'tokenserver.token_duration', DEFAULT_TOKEN_DURATION
    )
    try:
        requested_duration = int(request.params["duration"])
    except (KeyError, ValueError):
        pass
    else:
        if 0 < requested_duration < token_duration:
            token_duration = requested_duration

    token_data = {
        'uid': user['uid'],
        'node': user['node'],
        'expires': int(time.time()) + token_duration,
        'fxa_uid': request.validated['fxa_uid'],
        'device_id': request.validated['device_id']
    }
    token = tokenlib.make_token(token_data, secret=secret)
    secret = tokenlib.get_derived_secret(token, secret=secret)

    endpoint = pattern.format(
        uid=user['uid'],
        service=service,
        node=user['node']
    )

    # To help measure user retention, include the timestamp at which we
    # first saw this user as part of the logs.
    request.metrics['uid.first_seen_at'] = user['first_seen_at']

    return {
        'id': token,
        'key': secret,
        'uid': user['uid'],
        'hashed_fxa_uid': request.validated['fxa_uid'],
        'api_endpoint': endpoint,
        'duration': token_duration,
        'hashalg': tokenlib.DEFAULT_HASHMOD
    }
