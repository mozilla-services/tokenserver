from cornice import Service
import json

from pyramid.httpexceptions import HTTPUnauthorized
from pyramid.security import Authenticated, Allow, ALL_PERMISSIONS
from pyramid.security import authenticated_userid


def acl(request):
    return [(Allow, Authenticated, ALL_PERMISSIONS),]



auth = Service(name='token', path='/1.0/{appname}/token', acl=acl)

# do we want to push this in a conf file for v1 ?
supported_apps = ['sync']


# XXX should be in cornice
def _JError(request, status, errors):
    resp = request.response
    resp.status = status
    resp.content_type = 'application/json'
    return {'status': 'error', 'errors': errors}


def check_request(request):
    # authenticate XXX is that the right spot ?
    request['email'] = email = authenticated_userid(request)
    if email is None:
        raise HTTPUnauthorized()

    # getting the app name
    appname = request.matchdict['appname']
    if appname not in supported_apps:
        request.validated['appname'] = appname
    else:
        request.errors.add('url', 'appname', 'Unknown application')


@auth.get(validator=check_request)
def get_token(request):

    appname = request.validated['appname']
    email = request.validated['email']
    return {}
