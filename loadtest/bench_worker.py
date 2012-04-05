import time
import sys
from tokenserver.tests.support import (MockCryptoWorker, PurePythonRunner,
                                       sign_data)


def timed(msg):
    def _timed(func):
        def __timed(*args, **kw):
            sys.stdout.write(msg + '...')
            sys.stdout.flush()
            start = time.time()
            try:
                return func(*args, **kw)
            finally:
                sys.stdout.write('%.4f s\n' % (time.time() - start))
                sys.stdout.flush()
        return __timed
    return _timed


def job(hostname, data, runner):
    sig = sign_data(hostname, data)
    runner.check_signature(hostname=hostname, signed_data=data,
                           signature=sig, algorithm="DS128")


@timed("one single call")
def single(**kwargs):
    job(**kwargs)


if __name__ == '__main__':

    kwargs = dict(runner=PurePythonRunner(MockCryptoWorker()),
                  hostname='browserid.org',
                  data='NOBODY EXPECTS THE SPANISH INQUISITION!')
    single(**kwargs)
