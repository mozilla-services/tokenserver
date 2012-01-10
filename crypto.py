import hmac
import hashlib
import os
import binascii
import json
from hkdf import derive
from datetime import datetime, timedelta

_SIZE = 128
_HASH = hashlib.sha1


def generate_secret(size=_SIZE):
    return binascii.b2a_hex(os.urandom(size))[:size]


def sign(token, secret):
    if len(secret) != 128:
        raise ValueError("Invalid secret")
    token['signature'] = _signature(token, secret)
    return token


def _signature(token, secret):
    token = token.copy()
    if 'signature' in token:
        del token['signature']
    token = token.items()
    token.sort()
    return hmac.new(secret, json.dumps(token), _HASH).hexdigest()


def verify(token, secret):
    if len(secret) != 128:
        raise ValueError("Invalid secret")
    signature = token['signature']
    wanted = _signature(token, secret)
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
    token = {'uid': uid, 'expires': expires.isoformat()}
    sign(token, secret)
    return token


if __name__ == '__main__':
    print('Creating a secret')
    secret = generate_secret()
    print(secret)

    print('Derive the secret')
    dsecret = derive(secret, 128, salt="salted_value")
    print(dsecret)

    print('========= SERVER ==========')
    print('Creating the signed token')
    token = create_token('123', dsecret)
    print token

    print('creating a header with it')
    header = create_header(token)
    print header

    print('========= NODE ==========')
    print('extracting the token from the header')

    token = extract_token(header)
    print header

    print "validating the signature"

    verify(token, dsecret)
