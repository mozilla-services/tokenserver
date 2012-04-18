import sys

is_64bits = sys.maxsize > 2**32
major = '2'
minor = sys.version_info[1]
plat = sys.platform

root = 'http://chandlerproject.org/pub/Projects/MeTooCrypto/'

releases = {
  (False, 7, 'darwin'): root + 'M2Crypto-0.21.1-py2.7-macosx-10.8-intel.egg',
  (True, 5, 'darwin'): root + 'M2Crypto-0.21.1-py2.5-macosx-10.8-x86_64.egg',
  (False, 7, 'darwin'): root + 'M2Crypto-0.21.1-py2.7-macosx-10.7-intel.egg',
  (True, 7, 'darwin'): root + 'M2Crypto-0.21.1-py2.7-macosx-10.7-intel.egg',
  (True, 5, 'darwin'): root + 'M2Crypto-0.21.1-py2.5-macosx-10.7-x86_64.egg',
  (False, 5, 'darwin'): root + 'M2Crypto-0.21.1-py2.5-macosx-10.5-i386.egg',
  (True, 6, 'darwin'): root + 'M2Crypto-0.21.1-py2.6-macosx-10.6-universal.egg',
  (True, 5, 'darwin'): root + 'M2Crypto-0.21.1-py2.5-macosx-10.6-i386.egg',
  (True, 7, 'linux2'): 'http://ziade.org/M2Crypto-0.21.1-py2.7-linux-x86_64.egg',
  (True, 6, 'linux2'): 'http://ziade.org/M2Crypto-0.21.1-py2.6-linux-x86_64.egg',
  (False, 7, 'linux2'): 'http://ziade.org/M2Crypto-0.21.1-py2.7-linux-i386.egg',
  (False, 6, 'linux2'): 'http://ziade.org/M2Crypto-0.21.1-py2.6-linux-i386.egg',
}

print releases[is_64bits, minor, plat]
