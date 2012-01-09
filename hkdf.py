import math
import hashlib
import os
import binascii
import hmac


def sha_random(size=160):
    return binascii.b2a_hex(os.urandom(size))[:size]



class HKDF(object):
    """Implementation of the HMAC Key Derivation Function (HKDF) described
    on https://tools.ietf.org/html/rfc5869.
    """
    def __init__(self, hash=hashlib.sha1, salt=''):
        """
        :param salt: optional salt value (a non-secret random value).
                     If not provided, it is set to a string of Hashlen zeros.

        """
        self.hash = hash
        self.salt = salt
        self.hashlen = self.hash().digest_size
        self.salt.zfill(self.hashlen)

    def derive(self, ikm, size, info=None):
        prk = self.extract(ikm)
        return self.expand(prk, size, info)

    def extract(self, ikm):
        """
        Extract a pseudo random key (PRK) from the salt and the input keyring
        material (IKM)

        :param IKM: input keyring material

        Returns a pseudorandom key and its lenght
        """
        res = hmac.new(key=ikm, msg=self.salt, digestmod=self.hash)
        return res.hexdigest()

    def expand(self, prk, size, info=None):
        """Expand the given pseudo random key (PRK) to give the output keyring
        material.

        :param prk: the pseudo rando mkey
        :param size: the size of the output keyring material
        :param info: optional context and application specific information
                     (empty per default)

        Returns the output keyring material (OKM)
        """

        prev, output = "", ""
        steps = math.ceil(float(size) / self.hashlen)

        for step in range(int(steps)):
            prev = hmac.new(prk, prev + str(step), self.hash).hexdigest()
            output += prev

        return output


if __name__ == '__main__':
    salt = sha_random()
    hkdf = HKDF(salt=salt)
    key = 'somekey'

    print 'salt: %s' % salt
    print 'key: %s' % key
    print 'hkdfk: %s' % hkdf.derive(key, 128)
