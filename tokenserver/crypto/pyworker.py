import json
import sys
import os
import traceback

from powerhose.client.worker import Worker
from powerhose.util import unserialize
from powerhose.job import Job

from tokenserver import logger
from tokenserver.crypto.master import Response, PROTOBUF_CLASSES

from browserid._m2_monkeypatch import DSA as _DSA
from browserid._m2_monkeypatch import RSA as _RSA
from browserid import jwt
from browserid.certificates import CertificatesManager

from M2Crypto import BIO


class CertificatesManagerWithCache(CertificatesManager):

    def __init__(self, memory=None, memcache=None):
        if memory is None:
            memory = {}

        self.memory = memory
        self.memcache = memcache

    def __getitem__(self, hostname):
        """Get the certificate for the given hostname.

        If the certificate is not already in memory, try to get it in the
        shared memcache. If it's not in the the memcache, download it and store
        it both in memory and in the memcache.
        """
        try:
            # Use a cached key if available.
            return self.memory[hostname]
        except KeyError:
            # try to get the key from memcache if it doesn't exist in memory
                try:
                    # supposely the memcache lookup failed
                    raise KeyError()
                    key = self.memcache.get(hostname)
                    self.memory[hostname] = key
                    return key
                except KeyError:
                    # it doesn't exist in memcache either, so let's get it from
                    # the issuer host.
                    key = self.fetch_public_key(hostname)
                    #self.memcache.set(hostname, key)
                    self.memory[hostname] = key
                    return key


def get_crypto_obj(algo, filename=None, key=None):
    if filename is None and key is None:
        raise ValueError('you need to specify either filename or key')

    if key is not None:
        bio = BIO.MemoryBuffer(str(key))
    else:
        bio = BIO.openfile(filename)

    # we can know what's the algorithm used thanks to the filename
    if algo.startswith('RS'):
        obj = _RSA.load_pub_key_bio(bio)
    elif algo.startswith('DS'):
        obj = _DSA.load_pub_key_bio(bio)
    else:
        raise ValueError('unknown algorithm')
    return obj


def get_certificate(algo, filename=None, key=None):
    obj = get_crypto_obj(algo, filename, key)
    cls = getattr(jwt, '%sKey' % algo)
    return cls(obj=obj)


class CryptoWorker(object):

    def __init__(self):
        logger.info('starting a crypto worker')
        self.certs = CertificatesManagerWithCache()

    def __call__(self, msg):
        """proxy to the functions exposed by the worker"""
        logger.info('worker called with the message %s' % msg)
        try:
            if isinstance(msg, list):
                data = msg[0]
            else:
                data = msg

            data = unserialize(data)
            job = Job.load_from_string(data[-1])

            try:
                function_id, serialized_data = job.data.split('::', 1)
                obj = PROTOBUF_CLASSES[function_id]()
                obj.ParseFromString(serialized_data)
                data = {}
                for field, value in obj.ListFields():
                    data[field.name] = value

            except ValueError:
                raise ValueError('could not parse data')

            if not hasattr(self, function_id):
                raise ValueError('the function does not exists')

            res = getattr(self, function_id)(**data)
            return Response(value=res).SerializeToString()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            exc = traceback.format_tb(exc_traceback)
            exc.insert(0, str(e))
            return Response(error='\n'.join(exc)).SerializeToString()

    def error(self, message):
        """returns an error message"""
        raise Exception(message)

    def check_signature(self, hostname, signed_data, signature, algorithm):
        try:
            try:
                data = self.certs[hostname]
            except KeyError:
                self.error('unknown hostname "%s"' % hostname)

            cert = jwt.load_key(algorithm, data)
            return cert.verify(signed_data, signature)
        except:
            self.error('could not check sig for host %r' % hostname)
            raise

    def check_signature_with_cert(self, cert, signed_data, signature,
                                  algorithm):
        try:
            data = json.loads(cert)
            cert = jwt.load_key(algorithm, data)
            return cert.verify(signed_data, signature)
        except:
            self.error('could not check sig')
            raise

    def derivate_key(self):
        pass


def get_worker(endpoint, memcache=None, identity=None, prefix='tokenserver',
               worker=None):
    pid = str(os.getpid())
    if identity is None:
        identity = 'ipc:///tmp/tokenserver-slave-%s.ipc' % pid
    else:
        identity = identity.replace('$PID', pid)
    if worker is None:
        worker = CryptoWorker(memcache)
    return Worker(endpoint, identity, worker)


def main(worker=None):
    if len(sys.argv) < 1:
        raise ValueError("You should specify the zeromq and the memcache"
                         "endpoint")
    worker = get_worker(*sys.argv[1:], worker=worker)
    try:
        worker.run()
    finally:
        worker.stop()

if __name__ == '__main__':
    main()
