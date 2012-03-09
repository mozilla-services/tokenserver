from unittest import TestCase
import os

from tokenserver.crypto.pyworker import CryptoWorker
from tokenserver.tests.support import (
    CERTS_LOCATION,
    sign_data,
    PurePythonRunner
)


class TestPythonCryptoWorker(TestCase):

    def setUp(self):
        self.worker = CryptoWorker(path=CERTS_LOCATION)
        self.runner = PurePythonRunner(self.worker)
        self.assertEquals(len(self.worker.certs), 1)

    def test_check_signature(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        result = self.runner.check_signature(hostname=hostname,
                signed_data=data, signature=sig)
        self.assertTrue(result)

    def test_check_signature_with_key(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        filename = os.path.join(CERTS_LOCATION, 'browserid.org.RS256.crt')
        with open(filename, 'rb') as f:
            cert = f.read()

        result = self.runner.check_signature_with_cert(cert=cert,
                signed_data=data, signature=sig, algorithm='RS256')

        self.assertTrue(result)

    def test_key_derivation(self):
        return
        # result = self.call_worker('derivate_key')
