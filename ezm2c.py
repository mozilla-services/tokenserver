import sys

is_64bits = sys.maxsize > 2**32
major = '2'
minor = sys.version_info[1]
plat = sys.platform

HOST = "http://people.mozilla.com/~ametaireau/eggs/"

releases = {
  (False, 7, 'darwin'): 'M2Crypto-0.21.1-py2.7-macosx-10.8-intel.egg',
  (True, 5, 'darwin'): 'M2Crypto-0.21.1-py2.5-macosx-10.8-x86_64.egg',
  (False, 7, 'darwin'): 'M2Crypto-0.21.1-py2.7-macosx-10.7-intel.egg',
  (True, 7, 'darwin'): 'M2Crypto-0.21.1-py2.7-macosx-10.7-intel.egg',
  (True, 5, 'darwin'): 'M2Crypto-0.21.1-py2.5-macosx-10.7-x86_64.egg',
  (False, 5, 'darwin'): 'M2Crypto-0.21.1-py2.5-macosx-10.5-i386.egg',
  (True, 6, 'darwin'): 'M2Crypto-0.21.1-py2.6-macosx-10.6-universal.egg',
  (True, 5, 'darwin'): 'M2Crypto-0.21.1-py2.5-macosx-10.6-i386.egg',
  (True, 7, 'linux2'): 'M2Crypto-0.21.1-py2.7-linux-x86_64.egg',
  (True, 6, 'linux2'): 'M2Crypto-0.21.1-py2.6-linux-x86_64.egg',
  (False, 7, 'linux2'): 'M2Crypto-0.21.1-py2.7-linux-i686.egg',
  (False, 6, 'linux2'): 'M2Crypto-0.21.1-py2.6-linux-i686.egg',
}

try:
    print HOST + releases[is_64bits, minor, plat]
except KeyError:
    print 'http://pypi.python.org/packages/source/M/M2Crypto/M2Crypto-0.21.1.tar.gz'
