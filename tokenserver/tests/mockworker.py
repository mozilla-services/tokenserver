from tokenserver.tests.support import MockCryptoWorker
_class = None


def crypto_worker(job):
    global _class
    if _class is None:
        _class = MockCryptoWorker()
    return _class(job)
