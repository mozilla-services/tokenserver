import sys

is_64bits = sys.maxsize > 2**32
major = '2'
minor = sys.version_info[1]
plat = sys.platform

HOST = "http://people.mozilla.com/~ametaireau/eggs/"

releases = {
  (False, 6, 'darwin'): 'gevent-0.13.7-py2.6-macosx-10.7-intel.egg',
  (True, 6, 'darwin'): 'gevent-0.13.7-py2.6-macosx-10.7-intel.egg',
  (False, 7, 'darwin'): 'gevent_zeromq-0.2.0-py2.7-macosx-10.7-intel.egg',
  (True, 7, 'darwin'): 'gevent_zeromq-0.2.0-py2.7-macosx-10.7-intel.egg',
  (False, 6, 'linux2'): 'gevent_zeromq-0.2.0-py2.6.egg',
  (False, 7, 'linux2'): 'gevent_zeromq-0.2.0-py2.7.egg',
}

try:
    print HOST + releases[is_64bits, minor, plat]
except KeyError:
    print HOST + 'gevent_zeromq-0.2.0-py2.6.egg'
