# flake8: noqa
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
import fnmatch


runner = sys.argv[0]


import logging
from collections import defaultdict

from tokenserver.assignment import INodeAssignment

from mozsvc.config import get_configurator
from mozsvc.plugin import load_and_register, load_from_settings


logger = logging.getLogger('tokenserver')


def includeme(config):
    settings = config.registry.settings
    config.include("cornice")
    config.include("mozsvc")
    config.include("tokenserver.tweens")
    config.scan("tokenserver.views")

    # initializes the assignment backend
    load_and_register("tokenserver", config)

    # initialize the browserid backend if it exists
    if "browserid.backend" in settings:
        load_and_register("browserid", config)

    # initialize the oauth backend if it exists
    if "oauth.backend" in settings:
        load_and_register("oauth", config)

    # initialize node-type classifier
    load_node_type_classifier(config)

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

    # ensure the metrics_id_secret_key is an ascii string.
    id_key = settings.get('fxa.metrics_uid_secret_key')
    if id_key is None:
        logger.warning(
            'fxa.metrics_uid_secret_key is not set. '
            'This will allow PII to be more easily identified')
    elif isinstance(id_key, unicode):
        settings['fxa.metrics_uid_secret_key'] = id_key.encode('ascii')

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

    def __iter__(self):
        if not self._loaded:
            self.callable(self)
            self._loaded = True
        return super(LazyDict, self).__iter__()

    def keys(self):
        if not self._loaded:
            self.callable(self)
            self._loaded = True
        return super(LazyDict, self).keys()


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


def load_node_type_classifier(config):
    """Load fnmatch-style patterns for classifying node type.

    Given entries in a config file like this:

        [tokenserver]
        node_type_patterns =
            foo:*.foo.com
            bar:*bar*
            default:*

    Returns a classifier function that will take a string argument and
    return the name of the first matching pattern, or None if no patterns
    matched to string. Patterns are matched in the order specified in the
    config file.
    """
    settings = config.registry.settings
    patterns = settings.get('tokenserver.node_type_patterns', ())
    if isinstance(patterns, basestring):
        raise ValueError(
            "Expected 'tokenserver.node_type_patterns' to be a list")
    patterns = [p.split(":", 1) for p in patterns]
    # For easy matching, compile all the patterns together into a single regex.
    # A good regex engine would turn this into a single FSA to efficiently test
    # all patterns simultaneously. Python's regex engine will do a left-to-right
    # backtracking search, which is also fine for our purposes.
    regexes = []
    for label, pattern in patterns:
        regexes.append("(?P<{}>{})".format(label, fnmatch.translate(pattern)))
    try:
        regex = re.compile("|".join(regexes))
    except re.error:
        raise ValueError("Invalid node_type_patterns")

    def classify(node):
        # N.B. `match` always matches from the start of the string.
        m = regex.match(node)
        if m is None:
            return None
        return m.lastgroup

    settings['tokenserver.node_type_classifier'] = classify
    return classify


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()
