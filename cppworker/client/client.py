from powerhose import PowerHose
from response_pb2 import Response


def main():
    with PowerHose() as ph:
        # sending some jobs
        for i in xrange(1, 10, 4):
            status, result = ph.execute('derive_secret', '')
            if status != 'OK':
                print 'The job failed'
                print result
            else:
                res = Response.FromString(result)
                print res

    with PowerHose() as ph:
        print ph.execute('nothing', 'xxx')


if __name__ == "__main__":
    main()
