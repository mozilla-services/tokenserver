import json
import time
import os

from tokenserver.tests.mockworker import MockCryptoWorker
from browserid.tests.support import patched_key_fetching, fetch_public_key
from tokenserver.crypto.pyworker import (
    CryptoWorker,
    TTLedDict,
    CertificatesManagerWithCache,
    get_crypto_worker
)

from tokenserver.tests.support import (
    sign_data,
    PurePythonRunner,
)
from tokenserver.tests.support import unittest


class TestPythonCryptoWorker(unittest.TestCase):

    def setUp(self):
        self.worker = MockCryptoWorker()
        self.runner = PurePythonRunner(self.worker)

    def test_check_signature(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        result = self.runner.check_signature(hostname=hostname,
                signed_data=data, signature=sig, algorithm="DS128")
        self.assertTrue(result)

    def test_the_crypto_tester(self):
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
        # derivating the key twice with the same parameters should return the
        # same key.
        self.worker = CryptoWorker()
        self.runner = PurePythonRunner(self.worker)

        # taken from the tokenlib
        hashmod = "sha256"
        IKM = "0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        salt = "000102030405060708090a0b0c"
        info = "f0f1f2f3f4f5f6f7f8f9"
        L = 42
        OKM = "3cb25f25faacd57a90434f64d0362f2a"\
              "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"\
              "34007208d5b887185865"
        result = self.runner.derivate_key(ikm=IKM, salt=salt, info=info,
                                          l=L, hashmod=hashmod)
        self.assertEquals(result, OKM)
        return

        hashmod = 'sha1'
        IKM = "0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c".decode("hex")
        salt = None
        info = ""
        L = 42
        OKM = "2c91117204d745f3500d636a62f64f0a".decode("hex") +\
              "b3bae548aa53d423b0d1f27ebba6f5e5".decode("hex") +\
              "673a081d70cce7acfc48".decode("hex")

        result = self.runner.derivate_key(ikm=IKM, salt=salt, info=info,
                                          l=L, hashmod=hashmod)
        self.assertEquals(result, OKM)


class TestTTledDict(unittest.TestCase):

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
        self.assertFalse('foo' in cache)

        with self.assertRaises(KeyError):
            cache['foo']

        # we have a way to put never-expiring values in the cache
        cache['bar'] = 'baz'
        cache.set_ttl('bar', 0)
        time.sleep(1)
        self.assertEquals(cache['bar'], 'baz')


class TestCertificatesManager(unittest.TestCase):

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


class TestConfigurationLoading(unittest.TestCase):

    def test_get_crypto_worker(self):
        config_file = os.path.join(os.path.dirname(__file__),
                                   'cryptoworker.ini')
        worker = get_crypto_worker(CryptoWorker, config_file)
        self.assertTrue(worker.certs.loadtest_mode)
        self.assertEquals(worker.certs.memory.ttl, 160)
