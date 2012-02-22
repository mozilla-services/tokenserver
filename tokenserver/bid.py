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
