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

from browserid.utils import encode_bytes as encode_bytes_b64
from browserid.utils import decode_bytes as decode_bytes_b64
from cornice.errors import Errors


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


def parse_key_id(kid):
    """Parse an FxA key ID into its constituent timestamp and key hash."""
    keys_changed_at, key_hash = kid.split("-", 1)
    keys_changed_at = int(keys_changed_at)
    key_hash = decode_bytes_b64(key_hash)
    return (keys_changed_at, key_hash)


def format_key_id(keys_changed_at, key_hash):
    """Format an FxA key ID from a timestamp and key hash."""
    return "{:013d}-{}".format(
        keys_changed_at,
        encode_bytes_b64(key_hash),
    )
