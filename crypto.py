import hmac
import hashlib
import os
import binascii
import json
import time

_SIZE = 128


def generate_secret(size=_SIZE):
    return binascii.b2a_hex(os.urandom(size))[:size]


def sign(token, secret):
    if len(secret) != 128:
        raise ValueError("Invalid secret")
    token['signature'] = hmac.new(secret, '', hashlib.sha1).hexdigest()
    return token


def verify(token, secret):
    if len(secret) != 128:
        raise ValueError("Invalid secret")
    signature = token['signature']
    wanted = hmac.new(secret, '', hashlib.sha1).hexdigest()
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


def create_token(email, uid, node, secret, ttl=30):
    token =  {'timestamp': time.time(),
              'ttl': ttl,
              'email': email,
              'uid': uid,
              'node': node}
    sign(token, secret)
    return token


if __name__ == '__main__':
    print('Creating a secret')
    secret = generate_secret()
    print(secret)

    print('========= SERVER ==========')
    print('Creating the signed token')
    token = create_token('tarek@mozilla.com', '123', 'phx345', secret)
    print token

    print('creating a header with it')
    header = create_header(token)
    print header

    print('========= NODE ==========')
    print('extracting the token from the header')

    token = extract_token(header)
    print header

    print "validating the signature"

    verify(token, secret)
