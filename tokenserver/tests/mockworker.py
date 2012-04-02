from tokenserver.crypto.pyworker import CryptoWorker
from browserid.tests.support import patched_key_fetching


class MockCryptoWorker(CryptoWorker):
    """Test implementation of the crypto worker, using the patched certificate
    handling.
    """
    def check_signature(self, *args, **kwargs):
        with patched_key_fetching():
            return super(MockCryptoWorker, self)\
                    .check_signature(*args, **kwargs)


crypto_worker = MockCryptoWorker()
