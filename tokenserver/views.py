from pyramid.threadlocal import get_current_registry
from cornice import Service
from repoze.who.plugins.vepauth.tokenmanager import SignedTokenManager


discovery = Service(name='discovery', path='/')


@discovery.get()
def _discovery(request):
    return {'sync': '1.0'}


class NodeTokenManager(SignedTokenManager):
    def __init__(self, *args, **kw):
        super(NodeTokenManager, self).__init__(*args, **kw)
        self.sentry = -1

    def make_token(self, request, data):
        if self.sentry is -1:
            settings = get_current_registry().settings
            self.sentry = settings.get('token.service_entry')

        extra = {'service_entry': self.sentry}
        token, secret, __ = super(NodeTokenManager, self).make_token(request,
                                                                     data)
        return token, secret, extra
