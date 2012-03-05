# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import json
from base64 import b32encode
from hashlib import sha1

from pyramid.httpexceptions import HTTPError
from webob import Response


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
