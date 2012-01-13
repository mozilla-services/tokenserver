import sys
import random

from tokenserver.crypto import get_secrets, get_token

from powerhose.workers import create_pool
from powerhose.sender import Sender

USERS = range(1, 300)
NODES = map(lambda i: "phx%s" % i, range(50))


def main():
    items = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    master, sig_secret = get_secrets()

    def create_token(userid, node, **kwargs):
        return get_token(master, sig_secret, userid, node)

    create_pool(10, {'create_token': create_token})

    ventilator = Sender()

    for i in range(items):
        data = {'userid': random.choice(USERS),
                'node': random.choice(NODES),
                'func': 'create_token'}

        ventilator.execute(data)

    ventilator.stop()

if __name__ == '__main__':
    main()
