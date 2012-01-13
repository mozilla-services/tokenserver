from pyramid.config import Configurator


def includeme(config):
    config.include("cornice")
    config.scan("tokenserver.views")


def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include(includeme)
    return config.make_wsgi_app()
