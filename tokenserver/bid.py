import os
import json
import time
import signal
import base64
import sys

from pyramid.threadlocal import get_current_registry

from vep.verifiers.local import LocalVerifier
from vep.jwt import JWT

from zope.interface import implements, Interface

from powerhose import JobRunner
from powerhose.client.worker import Worker


class IPowerhoseRunner(Interface):

    def execute(*args, **kw):
        """ """

# global registry
# # XXX thread-safetiness ?

# XXX see https://github.com/Pylons/pyramid/issues/442
def bye(*args, **kw):
    stop_runners()
    sys.exit(1)

signal.signal(signal.SIGTERM, bye)
signal.signal(signal.SIGINT, bye)

_runners = {}


def stop_runners():
    for runner in _runners.values():
        runner.stop()


class PowerHoseRunner(object):
    implements(IPowerhoseRunner)

    def __init__(self, endpoint, **kw):
        self.endpoint = endpoint
        if self.endpoint not in _runners:
            _runners[self.endpoint] = JobRunner(self.endpoint)
        self.runner = _runners[self.endpoint]
        self.runner.start()
        time.sleep(0.1)

    def execute(self, *args, **kw):
        return self.runner.execute(*args, **kw)


def get_worker(endpoint):
    identity = 'ipc://%s' % os.getpid()

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

    return Worker(endpoint, identity, target)


class PowerHoseJWT(object):

    def __init__(self, algorithm, payload, signature, signed_data):
        self.algorithm = algorithm
        self.payload = payload
        self.signature = signature
        self.signed_data = signed_data
        self.runner = get_current_registry().getUtility(IPowerhoseRunner)

    def check_signature(self, key_data):
        """Check that the JWT was signed with the given key."""
        # XXX toy serialization + sending everything
        # will need to do much better
        job_data = {'algorithm': self.algorithm,
                     'key_data': key_data,
                     'signed_data': self.signed_data,
                     'signature': base64.b64encode(self.signature),
                     'payload': self.payload}

        job_id = 'verify-bid'
        job_data = json.dumps(job_data)
        res = self.runner.execute(job_id, job_data)
        res = json.loads(res)
        return res.get('res') == 1


class PowerHoseVerifier(LocalVerifier):

    def __init__(self, urlopen=None, trusted_secondaries=None, cache=None,
                 parser_cls=PowerHoseJWT):
        super(PowerHoseVerifier, self).__init__(urlopen, trusted_secondaries,
                                                cache, parser_cls)

    def verify(self, assertion):
        return super(PowerHoseVerifier, self).verify(assertion)
