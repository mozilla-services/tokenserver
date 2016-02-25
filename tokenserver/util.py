# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
from base64 import b32encode
from hashlib import sha1, sha256
import json
import hmac
import time

from pyramid.response import Response
from pyramid import httpexceptions as exc

from cornice.errors import Errors


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


def fxa_metrics_hash(value, hmac_key):
    """Derive FxA metrics id from user's FxA email address or whatever.

    This is used to obfuscate the id before logging it with the metrics
    data, as a simple privacy measure.
    """
    hasher = hmac.new(hmac_key, '', sha256)
    # value may be an email address, in which case we only want the first part
    hasher.update(value.split("@", 1)[0])
    return hasher.hexdigest()


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


def find_config_file(*paths):
    ini_files = []
    ini_files.append(os.environ.get('TOKEN_INI'))
    ini_files.extend(paths)
    ini_files.extend((
        '/data/tokenserver/token-prod.ini',
        '/etc/mozilla-services/token/production.ini',
    ))
    for ini_file in ini_files:
        if ini_file is not None:
            ini_file = os.path.abspath(ini_file)
            if os.path.exists(ini_file):
                return ini_file
    raise RuntimeError("Could not locate tokenserver ini file")


def get_timestamp():
    """Get current timestamp in milliseconds."""
    return int(time.time() * 1000)
