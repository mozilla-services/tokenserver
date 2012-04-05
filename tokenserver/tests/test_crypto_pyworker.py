import json
import time
from unittest import TestCase

from tokenserver.tests.mockworker import MockCryptoWorker
from browserid.tests.support import patched_key_fetching, fetch_public_key
from tokenserver.crypto.pyworker import (
    CryptoWorker,
    TTLedDict,
    ExpiredValue,
    CertificatesManagerWithCache
)
from tokenserver.tests.support import (
    sign_data,
    PurePythonRunner,
    patched_environ,
)


class TestPythonCryptoWorker(TestCase):

    def setUp(self):
        with patched_environ():
            self.worker = CryptoWorker()
            self.runner = PurePythonRunner(self.worker)

    def test_check_signature(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        with patched_key_fetching():
            sig = sign_data(hostname, data)
            result = self.runner.check_signature(hostname=hostname,
                    signed_data=data, signature=sig, algorithm="DS128")
        self.assertTrue(result)

    def test_the_crypto_tester(self):
        with patched_environ():
            self.worker = MockCryptoWorker()
            self.runner = PurePythonRunner(self.worker)

        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        result = self.runner.check_signature(hostname=hostname,
                signed_data=data, signature=sig, algorithm="DS128")
        self.assertTrue(result)

    def test_check_signature_with_key(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        cert = json.dumps(fetch_public_key(hostname))

        result = self.runner.check_signature_with_cert(cert=cert,
                signed_data=data, signature=sig, algorithm='DS128')

        self.assertTrue(result)

    def test_loadtest_mode(self):
        # when in loadtest mode, the crypto worker should be able to verify
        # signatures issued by loadtest.local
        with patched_environ():
            self.worker = CryptoWorker(loadtest_mode=True)
            self.runner = PurePythonRunner(self.worker)
        hostname = 'loadtest.local'
        data = "All your base are belong to us."

        signature = sign_data(hostname, data)

        # as you may have noticed, we are not mocking the key fetching here.
        result = self.runner.check_signature(hostname=hostname,
                signed_data=data, signature=signature, algorithm="DS128")

        self.assertTrue(result)

    def test_key_derivation(self):
        return
        # result = self.call_worker('derivate_key')


class TestTTledDict(TestCase):

    def test_ttled_dict(self):
        # setup a dict with an expiration of 100ms.
        cache = TTLedDict(1)
        # asking for something not defined raises an exception
        with self.assertRaises(KeyError):
            cache['foo']

        cache['foo'] = 'bar'

        # should be available just now
        self.assertEquals(cache['foo'], 'bar')
        # even if we are asking twice
        self.assertEquals(cache['foo'], 'bar')

        # but if we wait a bit more it should'n be present.
        time.sleep(1)
        with self.assertRaises(ExpiredValue):
            cache['foo']

        # we have a way to put never-expiring values in the cache
        cache['bar'] = 'baz'
        cache.set_ttl('bar', 0)
        time.sleep(1)
        self.assertEquals(cache['bar'], 'baz')


class TestCertificatesManager(TestCase):

    def test_without_memory_nor_memcache(self):
        # this should make a request each time
        with patched_key_fetching():
            cm = CertificatesManagerWithCache(memory=False, memcache=False)
            self.assertFalse(cm.memory)
            self.assertFalse(cm.memcache)
            cm['browserid.org']

    def test_memory(self):
        with patched_key_fetching():
            cm = CertificatesManagerWithCache(memcache=False)
            self.assertFalse(cm.memcache)
            self.assertEquals(len(cm.memory), 0)

            # getting something should populate the memory
            cm['browserid.org']
            self.assertEquals(len(cm.memory), 1)
