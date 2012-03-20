from powerhose.client.workers import Workers
import sys

if len(sys.argv) != 2:
    raise Exception('Bad number of args for workers - %s' % str(sys.argv))

workers = Workers(sys.argv[1])
try:
    workers.run()
except KeyboardInterrupt:
    workers.stop()
