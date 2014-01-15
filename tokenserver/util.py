# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from base64 import b32encode
from hashlib import sha1
import os
import sys
import json

from pyramid.threadlocal import get_current_registry
from pyramid.response import Response
from pyramid import httpexceptions as exc

from cornice.errors import Errors

from mozsvc.secrets import Secrets


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


def hash_email(email):
    digest = sha1(email.lower()).digest()
    return b32encode(digest).lower()


class _JSONError(exc.HTTPError):
    def __init__(self, errors, status_code=400, status_message='error'):
        body = {'status': status_message, 'errors': errors}
        Response.__init__(self, json.dumps(body))
        self.status = status_code
        self.content_type = 'application/json'


def json_error(status_code=400, status_message='error', **kw):
    errors = Errors(status=status_code)
    kw.setdefault('location', 'body')
    kw.setdefault('name', '')
    kw.setdefault('description', '')
    errors.add(**kw)
    return _JSONError(errors, status_code, status_message)


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
