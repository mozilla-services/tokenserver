from tokenserver.tests.support import MockCryptoWorker
from tokenserver.crypto.pyworker import get_crypto_worker
from powerhose import get_params


_class = None


def crypto_worker(job):
    global _class
    if _class is None:
        config_file = get_params()['config']
        _class = get_crypto_worker(MockCryptoWorker, config_file)
    return _class(job)
