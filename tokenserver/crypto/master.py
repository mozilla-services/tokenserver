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

from powerhose.client.workers import Workers


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
_workers = {}


def stop_runners():
    for workers in _workers.values():
        workers.stop()
    for runner in _runners.values():
        runner.stop()


class PowerHoseRunner(object):
    implements(IPowerhoseRunner)

    def __init__(self, endpoint, workers_cmd, **kw):
        self.endpoint = endpoint
        self.workers_cmd = workers_cmd
        if self.endpoint not in _runners:
            _runners[self.endpoint] = JobRunner(self.endpoint)
            _workers[self.endpoint] = Workers(self.workers_cmd)
        self.runner = _runners[self.endpoint]
        self.runner.start()
        time.sleep(.5)
        self.workers = _workers[self.endpoint]
        self.workers.run()

    def execute(self, *args, **kw):
        return self.runner.execute(*args, **kw)
