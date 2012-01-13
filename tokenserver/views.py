from cornice import Service
from pyramid.httpexceptions import HTTPUnauthorized


auth = Service(name='token', path='/1.0/{appname}/token')


@auth.get()
def get_token(request):
    # XXX return a token
    return HTTPUnauthorized()
