# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import sys


def monkey_patch_gevent():
    """Monkey-patch gevent into core and zmq."""
    try:
        from gevent import monkey
    except ImportError:
        return
    monkey.patch_all()
    try:
        import zmq
        import zmq.eventloop
        import zmq.eventloop.ioloop
        import zmq.eventloop.zmqstream
        import zmq.green
        import zmq.green.eventloop
        import zmq.green.eventloop.ioloop
        import zmq.green.eventloop.zmqstream
    except ImportError:
        return
    TO_PATCH = ((zmq, zmq.green),
                (zmq.eventloop, zmq.green.eventloop),
                (zmq.eventloop.ioloop, zmq.green.eventloop.ioloop),
                (zmq.eventloop.zmqstream, zmq.green.eventloop.zmqstream))
    for (red, green) in TO_PATCH:
        for name in dir(red):
            redval = getattr(red, name)
            if name.startswith('__') or type(redval) is type(zmq):
                continue
            try:
                greenval = getattr(green, name)
            except AttributeError:
                continue
            if redval is not greenval:
                setattr(red, name, greenval)


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
    monkey_patch_gevent()

    config.include("cornice")
    config.include("mozsvc")
    config.scan("tokenserver.views")
    settings = config.registry.settings

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

    # load the secrets file(s)
    key = 'tokenserver.secrets_file'
    secret_file = settings[key]
    if not isinstance(secret_file, list):
        secret_file = [secret_file]

    files = []
    for line in secret_file:
        secret_file = [file for file in [file.strip() for file in line.split()]
                       if file != '']
        files.extend(secret_file)

    settings[key] = Secrets(files)
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
