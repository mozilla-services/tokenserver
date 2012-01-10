#!/usr/bin/env python
"""This test had been taken from pycryptopp (thus licenced under GPL)

See http://tahoe-lafs.org/trac/pycryptopp/attachment/ticket/42
"""
#!/usr/bin/env python

import re
import unittest
import hashlib

from binascii import a2b_hex, b2a_hex
import hkdf


TEST_HKDF_RE = re.compile("\nCOUNT=([0-9]+)\nHASH=([0-9A-Z]+)\nIKM=([0-9a-f]+)"
                          "\nSALT=([0-9a-z ]+)\nINFO=([0-9a-z ]+)\nL=([0-9]+)"
                          "\nPRK=([0-9a-f]+)\nOKM=([0-9a-f]+)")


class HKDFTest(unittest.TestCase):

    def test_HKDF(self):
        # The test vector is from RFC 5869 (HMAC-based Extract-and-Expand
        # Key Derivation Function (HKDF))'s
        # Appendix A. Test Vectors
        # http://tools.ietf.org/html/rfc5869
        curfile = open('HKDFMsg.txt', 'r')
        s = curfile.read()
        print s, "\n"
        return self._test_HKDF(s)

    def _test_HKDF(self, vects_str):

        for mo in TEST_HKDF_RE.finditer(vects_str):
            count = int(mo.group(1))
            print "test hdkf: ", count, "\n"

            hashalg = str(mo.group(2))

            if hashalg == "SHA256":
                print "this is sha256\n"
                hash = hashlib.sha256

            elif hashalg == "SHA1":
                print "this is sha1\n"
                hash = hashlib.sha1

            ikm = a2b_hex(mo.group(3))
            salttmp = mo.group(4)

            if salttmp == "none":
                salt = None
            elif salttmp == "zero length":
                salt = ""
            else:
                salt = a2b_hex(salttmp)

            infotmp = mo.group(5)
            if infotmp == "zero length":
                info = ""
            else:
                info = a2b_hex(infotmp)

            l = int(mo.group(6))

            prk = a2b_hex(mo.group(7))
            okm = a2b_hex(mo.group(8))

            hk = hkdf.HKDF(salt, hash)
            computedprk = hk.extract(ikm)
            self.failUnlessEqual(computedprk, prk,
                "computedprk: %s, prk: %s" % (b2a_hex(computedprk),
                                              b2a_hex(prk)))

            computedokm = hk.expand(computedprk, l, info)
            self.failUnlessEqual(computedokm, okm,
                "computedokm: %s, okm: %s" % (b2a_hex(computedokm),
                                              b2a_hex(okm)))

if __name__ == "__main__":
    unittest.main()
