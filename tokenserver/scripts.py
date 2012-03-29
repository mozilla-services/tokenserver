import sys
from tokenserver.util import (
    generate_secret as _generate_secret,
    display_secrets as _display_secrets
)


def generate_secret():
    if len(sys.argv) != 3:
        raise ValueError('You need to specify the path to the secret file '
                         'and the name of the node.')
    node, secret = _generate_secret(*sys.argv[1:])
    print('Inserted a new secret for node %s: %s' % (node, secret))


def display_secrets():
    if len(sys.argv) < 2:
        raise ValueError('You need to specify the path to the secret file')
    _display_secrets(*sys.argv[1:])
