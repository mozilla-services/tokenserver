from Crypto.Hash import MD5, HMAC
import math


class HKDF(object):
    """Implementation of the HMAC Key Derivation Function (HKDF) described
    on https://tools.ietf.org/html/rfc5869.
    """

    def derive(self, ikm, size, salt=None, hashalg=None, info=None):
        prk = self.extract(ikm, salt, hashalg)
        okm = self.expand(prk, size, info)

        return okm

    def extract(self, ikm, salt=None, hashalg=None):
        """
        Extract a pseudo random key (PRK) from the salt and the input keyring
        material (IKM)

        :param salt: optional salt value (a non-secret random value).
                     If not provided, it is set to a string of Hashlen zeros.

        :param IKM: input keyring material

        Returns a pseudorandom key and its lenght
        """
        # default values
        self.hashalg = hashalg or MD5  # default
        salt = salt or ""

        # get the hash lenght
        self.hashlen = self.hashalg.new().digest_size
        salt.zfill(self.hashlen)

        hmac = HMAC.new(salt, ikm, hashalg)
        prk = hmac.digest()
        return prk

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
            prev = HMAC.new(prk, prev + str(step), self.hashalg)
            output += prev.digest()

        return output


if __name__ == '__main__':
    hkdf = HKDF()
    print hkdf.derive(MD5.new().digest(), 15)
