# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import logging
from ConfigParser import NoSectionError
from collections import defaultdict

from mozsvc.config import get_configurator
from mozsvc.plugin import load_and_register
from tokenlib.secrets import Secrets


logger = logging.getLogger('tokenserver')


def includeme(config):
    config.include("cornice")
    config.include("mozsvc")
    config.scan("tokenserver.views")

    # initializes the assignment backend
    load_and_register("tokenserver", config)

    # initialize the powerhose and browserid backends if they exist
    for section in ("powerhose", "browserid"):
        try:
            load_and_register(section, config)
        except NoSectionError:
            pass

    # load apps and set them up back in the setting
    settings = config.registry.settings
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

    # load the secrets file
    key = 'tokenserver.secrets_file'
    settings[key] = Secrets(settings[key])


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()
