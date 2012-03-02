from unittest import TestCase
import os

from tokenserver.crypto.pyworker import CryptoWorker, Response, get_crypto_obj
from tokenserver.crypto.pyworker import _RSA, PROTOBUF_CLASSES
from vep import jwt


CERTS_LOCATION = os.path.join(os.path.dirname(__file__), 'certs')


def sign_data(hostname, data, alg='RS', key=None):
    # load the cert with the private key
    filename = os.path.join(CERTS_LOCATION, '%s.key' % hostname)
    obj = _RSA.load_key(filename)
    cert = jwt.RS256Key(obj=obj)
    return cert.sign(data)


class TestPythonCryptoWorker(TestCase):

    def setUp(self):
        self.worker = CryptoWorker(path=CERTS_LOCATION)
        self.assertEquals(len(self.worker.certs), 1)

    def test_check_signature(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        result = self.call_worker('check_signature', hostname=hostname,
                                  signed_data=data, signature=sig)
        self.assertTrue(result)

    def test_check_signature_with_key(self):
        hostname = 'browserid.org'
        data = 'NOBODY EXPECTS THE SPANISH INQUISITION!'

        sig = sign_data(hostname, data)
        filename = os.path.join(CERTS_LOCATION, 'browserid.org.RS256.crt')
        with open(filename, 'rb') as f:
            cert = f.read()

        result = self.call_worker('check_signature_with_cert', cert=cert,
                                  signed_data=data, signature=sig,
                                  algorithm='RS256')
        self.assertTrue(result)

    def test_key_derivation(self):
        return
        result = self.call_worker('derivate_key')

    def call_worker(self, function_id, **data):
        """utility dealing with serialisation / deserialisation and calling
        the python worker with the right function id
        """
        # send a message encoded with json. It is a nested dict, containing
        # first the identifier of the function to call and then the data to send
        # to this particular function.

        obj = PROTOBUF_CLASSES[function_id]()
        for key, value in data.items():
            setattr(obj, key, value)

        serialized_resp = self.worker("::".join((function_id,
                                                 obj.SerializeToString())))
        resp = Response()
        resp.ParseFromString(serialized_resp)

        if resp.error:
            raise Exception(resp.error)
        else:
            return resp.value
