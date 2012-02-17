import urllib2
import json


class _Resp(object):
    def __init__(self, data='', code=200):
        self.data = data
        self.code = code
        self.headers = {}

    def read(self):
        return self.data

    def getcode(self):
        return self.code


class RegPatcher(object):

    def _response(self, req, *args, **kw):
        url = req.get_full_url()
        if not url.endswith('sync'):
            res = 'kismw365lo7emoxr3ohojgpild6lph4b'
        else:
            res = 'http://phx324'

        return _Resp(json.dumps(res))

    def setUp(self):
        self.old = urllib2.urlopen
        urllib2.urlopen = self._response
        super(RegPatcher, self).setup()

    def tearDown(self):
        urllib2.urlopen = self.old
        super(RegPatcher, self).tearDown()
