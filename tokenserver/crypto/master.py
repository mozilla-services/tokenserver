import functools
import thread
import os

from zope.interface import implements, Interface
from pyramid.threadlocal import get_current_registry

from powerhose.client import Pool
from google.protobuf.message import DecodeError

from tokenserver.crypto.messages import (
    CheckSignature,
    CheckSignatureWithCert,
    Response
)

# association between the function names and the appropriate protobuf classes
PROTOBUF_CLASSES = {
    'check_signature': CheckSignature,
    'check_signature_with_cert': CheckSignatureWithCert
}


# interface to be able to register the powerhose worker and retrieve it in the
# registry
class IPowerhoseRunner(Interface):
    pass


def get_runner():
    """Utility function returning the powerhose runner actually in the
    registry.
    """
    return get_current_registry().getUtility(IPowerhoseRunner)


class PowerHoseRunner(object):
    """Implements a simple powerhose runner.

    This class is the one spawning the powerhose master and the workers, if
    any need to be created.

    You need to instanciate this class with the following parameters::

        >>> runner = PowerHoseRunner(endpoint, workers_cmd)

    :param endpoint: the zmq endpoint used to communicate between the powerhose
                     master process and the workers.

    This class also provides methods to ease the communication with the
    workers. You can directly send information to the workers by using the
    methods defined in "methods".

    This allows to make calls directly to this object. IOW, it is possible
    to call the methods listed in "methods" on the object::

        >>> runner.check_signature(**args)

    However, all the arguments need to be passed as keyword arguments.
    """
    # We implement an interface to be able to retrieve the object with the
    # pyramid registry system. This means that this class will only be
    # instanciated once, and this instance will be returned each time.
    implements(IPowerhoseRunner)

    methods = ['derivate_key', 'check_signature', 'check_signature_with_cert']

    def __init__(self, endpoint, **kw):
        pid = str(os.getpid())
        self.endpoint = endpoint.replace('$PID', pid)
        self.pool = Pool(int(kw.get('pool_size', 5)), self.endpoint)

    def execute(self, data):
        return self.pool.execute(data)

    def __getattr__(self, attr):
        """magic method getter to be able to do direct function calls on this
        object.
        """
        if attr in self.methods:
            return functools.partial(self._execute, attr)
        return super(PowerHoseRunner, self).__getattribute__(attr)

    def _execute(self, function_id, **data):
        """Send a message to the underlying runner.

        This is the low level function, and shouldn't be used directly as-is.
        You should use the high level messages to send crypto works to the
        workers.

        This function takes care of the serialisation / deserialization,
        depending the function given.

        In the eventuality that the invoked function returns an error, an
        exception will be raised.

        :param function_id: the name of the function to be invoked.
        :param data: the parameters to send to the function.
        """
        obj = PROTOBUF_CLASSES[function_id]()
        for key, value in data.items():
            setattr(obj, key, value)

        # XXX use headers here
        data = "::".join((function_id, obj.SerializeToString()))
        serialized_resp = self.execute(data)
        resp = Response()
        try:
            resp.ParseFromString(serialized_resp)
        except DecodeError:
            raise Exception(serialized_resp)

        if resp.error:
            raise Exception(resp.error)
        else:
            return resp.value
