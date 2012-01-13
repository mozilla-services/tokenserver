import hmac
import hashlib
import os
import binascii
import json
from datetime import datetime, timedelta
import time

from tokenserver.hkdf import derive

_SIZE = 256
_HASH = hashlib.sha1


def random_value(size=_SIZE):
    return binascii.b2a_hex(os.urandom(size))[:size]


def sign(token, secret, key='signature'):
    if len(secret) != _SIZE:
        raise ValueError("Invalid secret")
    token[key] = _signature(token, secret, key)
    return token


def oauth_sign(token, secret):
    token['oauth_timestamp'] = time.time()
    token['oauth_nonce'] = random_value(128)
    token = sign(token, secret, key='oauth_signature')
    token['oauth_signature_method'] = 'HMAC-SHA1'  # XXX
    return token


def _signature(token, secret, key='signature'):
    token = token.copy()
    if key in token:
        del token[key]
    token = token.items()
    token.sort()
    return hmac.new(secret, json.dumps(token), _HASH).hexdigest()


def verify(token, secret, key="signature"):
    if len(secret) != _SIZE:
        raise ValueError("Invalid secret")
    signature = token[key]
    wanted = _signature(token, secret, key)
    if signature != wanted:
        raise ValueError('Invalid Token')


def create_header(token):
    return 'Authorization: MozToken %s' % json.dumps(token)


def extract_token(header):
    if not header.startswith('Authorization: MozToken '):
        raise ValueError("Invalid token")
    token = header[len('Authorization: MozToken '):]
    try:
        token = json.loads(token)
    except ValueError:
        raise ValueError("Invalid token")
    return token


def create_token(uid, secret, expires=None):
    if expires is None:
        expires = datetime.now() + timedelta(minutes=30)
    token = {'uid': uid, 'expires': time.mktime(expires.timetuple())}
    sign(token, secret)
    return token


def create_token_info(token, token_secret, salt, node, metadata=None):
    info = {
        'oauth_consumer_key': token,
        'oauth_consumer_secret': token_secret,
        'salt': salt,
        'app_node': node,
    }

    if metadata is not None:
        info['app_metadata'] = metadata

    return info


def get_secrets():
    master = random_value()
    sig_secret = derive(master, _SIZE, salt="SIGN")

    return master, sig_secret


def get_token(master, sig_secret, idx, node):
    salt = random_value()  # XXX define what's the salt lenght

    auth_token = create_token(idx, sig_secret)
    token_secret = derive(master, _SIZE, salt=salt)

    return create_token_info(auth_token, token_secret, salt, node)


if __name__ == '__main__':
    import sys

    master, sig_secret = get_secrets()
    for x in range(int(sys.argv[1])):
        print("Generates a token")
        print(get_token(master, sig_secret, 123, "phx2"))
