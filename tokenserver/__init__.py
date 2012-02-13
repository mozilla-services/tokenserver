# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from repoze.who.plugins.vepauth.tokenmanager import SignedTokenManager
from pyramid.threadlocal import get_current_registry
from mozsvc.config import get_configurator


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


def includeme(config):
    config.include("cornice")
    config.include("mozsvc")
    config.include("pyramid_whoauth")
    config.scan("tokenserver.views")


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()
