import time
import signal
import sys
from functools import partial
import threading
import json

from zope.interface import implements, Interface

from powerhose.jobrunner import JobRunner
from powerhose.client.workers import Workers
from powerhose import logger



# interface to be able to register the powerhose worker and retrieve it in the
# registry
class IPowerhoseRunner(Interface):
    pass


# some signal handling to exit when on SIGINT or SIGTERM
def bye(*args, **kw):
    stop_runners()
    sys.exit(1)

signal.signal(signal.SIGTERM, bye)
signal.signal(signal.SIGINT, bye)

# to keep track of the runners and workers already instanciated
_runners = {}
_workers = {}


def stop_runners():
    logger.debug("stop_runner starts")

    for workers in _workers.values():
        workers.stop()

    logger.debug("workers killed")

    for runner in _runners.values():
        logger.debug('Stopping powerhose master')
        runner.stop()

    logger.debug("stop_runner ends")


class CryptoWorkers(threading.Thread):
    """Class to spawn powerhose worker in a separate thread"""
    def __init__(self, workers_cmd, num_workers, working_dir, env, **kw):
        threading.Thread.__init__(self)
        self.workers = Workers(workers_cmd, num_workers=num_workers,
                               working_dir=working_dir, env=env, **kw)

    def run(self):
        logger.debug('Starting powerhose workers')
        self.workers.run()

    def stop(self):
        logger.debug('Stopping powerhose workers')
        self.workers.stop()
        self.join()


class PowerHoseRunner(object):
    """Implements a simple powerhose runner.

    This class is the one spawning the powerhose master and the workers, if
    any need to be created.

    You need to instanciate this class with the following parameters::

        >>> runner = PowerHoseRunner(endpoint, workers_cmd)

    :param endpoint: the zmq endpoint used to communicate between the powerhose
                     master process and the workers.
    :param workers_cmd: the command to run in the workers.
    :param num_workers: the number of workers to spawn
    :param working_dir: the working directory
    :param env: additional environment variables. Can either be a dict or a
                string with the following syntax:
                "ENV_VAR=value;ENV_VAR2=value". This is to be able to load this
                class with settings coming from an ini file.


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

    def __init__(self, endpoint, workers_cmd, num_workers=5, working_dir=None,
                 env=None):

        # initialisation
        self.endpoint = endpoint
        self.workers_cmd = workers_cmd
        envdict = {}

        if env is not None:
            for pair in env.split(';'):
                key, value = pair.split('=', 1)
                envdict[key] = value

        if self.endpoint not in _runners:
            _runners[self.endpoint] = JobRunner(self.endpoint)
            _workers[self.endpoint] = CryptoWorkers(self.workers_cmd,
                                                    num_workers=num_workers,
                                                    working_dir=working_dir,
                                                    env=envdict)
        self.runner = _runners[self.endpoint]
        logger.debug('Starting powerhose master')

        # start the runner ...
        self.runner.start()
        time.sleep(.5)
        self.workers = _workers[self.endpoint]

        # ... and the workers
        self.workers.start()

    def __getattr__(self, attr):
        """magic method getter to be able to do direct function calls on this
        object.
        """
        if attr in self.methods:
            return self.execute(partial(self.execute, attr))
        raise KeyError()

    def encode_data(self, **data):
        return json.dumps(data)

    def decode_data(self, data):
        return json.loads(data)

    def execute(self, job_id, *args, **kwargs):
        data = self.runner.execute(job_id, self.encode_data(*args, **kwargs))
        return self.decode_data(data)


if __name__ == '__main__':
    runner = JobRunner(sys.argv[1])
    runner.start()
