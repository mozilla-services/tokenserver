from pyramid.config import Configurator
from tokenserver.bidauth import BrowserIDPolicy


def includeme(config):
    config.include("cornice")
    config.scan("tokenserver.views")


def main(global_config, **settings):
    bid = BrowserIDPolicy('dummy')

    config = Configurator(settings=settings,
                          authentication_policy=bid)
    config.include(includeme)
    return config.make_wsgi_app()
