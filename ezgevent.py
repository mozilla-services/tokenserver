import sys

is_64bits = sys.maxsize > 2**32
major = '2'
minor = sys.version_info[1]
plat = sys.platform


releases = {
  (False, 6, 'darwin'): 'http://ziade.org/gevent-0.13.7-py2.6-macosx-10.7-intel.egg',
  (True, 6, 'darwin'): 'http://ziade.org/gevent-0.13.7-py2.6-macosx-10.7-intel.egg',
  (False, 7, 'darwin'): 'http://ziade.org/gevent-0.13.7-py2.7-macosx-10.7-intel.egg',
  (True, 7, 'darwin'): 'http://ziade.org/gevent-0.13.7-py2.7-macosx-10.7-intel.egg',
}

try:
    print releases[is_64bits, minor, plat]
except KeyError:
    print 'http://pypi.python.org/packages/source/g/gevent/gevent-0.13.7.tar.gz'
