from powerhose.client.workers import Workers
import sys


workers = Workers(sys.argv[1])
try:
    workers.run()
except KeyboardInterrupt:
    workers.stop()
