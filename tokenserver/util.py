# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import json
from base64 import b32encode
from hashlib import sha1
import os

from pyramid.httpexceptions import HTTPError
from pyramid.threadlocal import get_current_registry
from webob import Response

from mozsvc.secrets import Secrets


def hash_email(email):
    digest = sha1(email.lower()).digest()
    return b32encode(digest).lower()


class JsonError(HTTPError):
    def __init__(self, status=400, location='body', name='', description=''):
        body = {'status': status, 'errors':
                [{'location': location, 'name': name,
                  'description': description}]
                }
        Response.__init__(self, json.dumps(body))
        self.status = status
        self.content_type = 'application/json'


# XXXX needs to move into mozsvc.secrets.Secrets
def generate_secret(filename, node):
    """Generates a new secret for the given node and saves it to a secrets
    file.

    :param filename: the complete path to the filename we want to put the
                     secret into.
    :param node: the node we want to generate the secret for.
    """
    if os.path.exists(filename):
        secrets = Secrets(filename)
    else:
        secrets = Secrets()

    secrets.add(node)
    secrets.save(filename)
    return node, secrets.get(node)[0]


# XXXX needs to move into mozsvc.secrets.Secrets
def display_secrets(filename, node=None):
    """Read a secret file and return its content.

    If a node is specified, return only the information for this node

    :param filename: the filename to read from
    :param node: only display the records for this node (optional)
    """
    def _display_node(secrets, node):
        # sort the records by timestamp and display them
        records = list(secrets._secrets[node])
        records.sort()

        print("%s secrets for %s" % (len(records), node))
        for timestamp, secret in records:
            print("- %s" % secret)

    secrets = Secrets(filename)
    if node is not None:
        _display_node(secrets, node)
    else:
        for node in secrets._secrets:
            _display_node(secrets, node)


def get_logger():
    return get_current_registry()['metlog']
