import json
import base64
import sys
import os

from vep.jwt import JWT

from powerhose.client.worker import Worker


def target(msg):
    try:
        data = json.loads(msg[1])
    except Exception:
        return json.dumps({'err': 'could not load json'})

    if data['key_data']['algorithm'] == 'RS':
        return json.dumps({'res': 1})
    try:
        jwt = JWT(data['algorithm'], data['payload'],
                base64.b64decode(data['signature']),
                data['signed_data'])
    except Exception:
        return json.dumps({'err': 'could not create jwt class'})
    try:
        res = jwt.check_signature(data['key_data'])
        return json.dumps({'res': res})
    except:
        return json.dumps({'err': 'could not check sig'})


def get_worker(endpoint, prefix='tokenserver'):
    identity = 'ipc://%s-%s' % (prefix, os.getpid())
    return Worker(endpoint, identity, target)


if __name__ == '__main__':
    worker = get_worker(sys.argv[1])
    try:
        worker.run()
    finally:
        worker.stop()
