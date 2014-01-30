# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from tokenserver.util import monkey_patch_gevent


runner = sys.argv[0]
if runner.endswith('nosetests'):
    monkey_patch_gevent()


import logging
from ConfigParser import NoSectionError
from collections import defaultdict

from tokenserver.assignment import INodeAssignment

from metlog.logging import hook_logger

from mozsvc.config import get_configurator
from mozsvc.plugin import load_and_register, load_from_settings
from mozsvc.secrets import Secrets


logger = logging.getLogger('tokenserver')


def includeme(config):
    settings = config.registry.settings
    if settings.get('tokenserver.monkey_patch_gevent', True):
        monkey_patch_gevent()

    config.include("cornice")
    config.include("mozsvc")
    config.include("tokenserver.tweens")
    config.scan("tokenserver.views")

    # default metlog setup
    if 'metlog.backend' not in settings:
        settings['metlog.backend'] = 'mozsvc.metrics.MetlogPlugin'
        settings['metlog.enabled'] = True
        settings['metlog.sender_class'] = \
                'metlog.senders.StdOutSender'

    metlog_wrapper = load_from_settings('metlog', settings)

    if settings['metlog.enabled']:
        for logger in ('tokenserver', 'mozsvc', 'powerhose'):
            hook_logger(logger, metlog_wrapper.client)

    config.registry['metlog'] = metlog_wrapper.client

    # initializes the assignment backend
    load_and_register("tokenserver", config)

    # initialize the powerhose and browserid backends if they exist
    for section in ("powerhose", "browserid"):
        try:
            load_and_register(section, config)
        except NoSectionError:
            pass

    # load apps and set them up back in the setting
    key = 'tokenserver.applications'
    applications = defaultdict(list)
    for element in settings.get(key, '').split(','):
        element = element.strip()
        if element == '':
            continue
        element = element.split('-')
        if len(element) != 2:
            continue
        app, version = element
        applications[app].append(version)

    settings[key] = applications

    # load the secrets backend, with a b/w-compat hook
    # for the old 'secrets_file' setting.
    secrets_file = settings.get('tokenserver.secrets_file')
    if secrets_file is not None:
        if 'tokenserver.secrets.backend' in settings:
            raise ValueError("can't use secrets_file with secrets.backend")
        if isinstance(secrets_file, basestring):
            secrets_file = secrets_file.split()
        settings['tokenserver.secrets.backend'] = 'mozsvc.secrets.Secrets'
        settings['tokenserver.secrets.filename'] = secrets_file
    secrets = load_from_settings('tokenserver.secrets', settings)
    settings['tokenserver.secrets'] = secrets

    read_endpoints(config)


class LazyDict(dict):
    def __init__(self, callable):
        self.callable = callable
        self._loaded = False

    def __getitem__(self, name):
        if not self._loaded:
            self.callable(self)
            self._loaded = True
        return super(LazyDict, self).__getitem__(name)


def load_endpoints(mapping, config):
    patterns = dict([(key.split('.', 1)[-1], value)
                        for key, value in config.registry.settings.items()
                        if key.startswith('endpoints.')])
    mapping.update(patterns)

    if len(mapping) == 0:
        # otherwise, try to ask the assignment backend the list of
        # endpoints
        backend = config.registry.getUtility(INodeAssignment)
        mapping.update(backend.get_patterns())


def read_endpoints(config):
    """If there is a section "endpoints", load it the format is
    service-version = pattern, and a dict will be built with those.
    """
    def _read(mapping):
        load_endpoints(mapping, config)

    config.registry['endpoints_patterns'] = LazyDict(_read)


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()
