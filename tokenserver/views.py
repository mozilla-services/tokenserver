from cornice import Service
import json

from pyramid.httpexceptions import HTTPUnauthorized


auth = Service(name='token', path='/1.0/{appname}/token')

# do we want to push this in a conf file for v1 ?
supported_apps = ['sync']


# XXX should be in cornice
def _JError(request, status, msg):
    resp = request.response
    resp.status = status
    resp.content_type = 'application/json'
    return {'status': 'error', 'errors': [msg]}


def check_request(request):
    appname = request.matchdict['appname']
    request.validated['appname'] = appname


@auth.get(validator=check_request)
def get_token(request):
    if request.validated['appname'] not in supported_apps:
        return _JError(request, 404, 'Unknown application')

    # XXX return a token
    return HTTPUnauthorized()
