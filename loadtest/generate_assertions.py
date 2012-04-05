from tokenserver.tests.support import get_assertion
import time


def generate_assertions():
    in_one_day = int(time.time() + 60 * 60 * 24) * 1000
    stream = 'VALID_ASSERTION = "%s"\n' % \
            get_assertion('alexis@loadtest.local', issuer='loadtest.local',
                          exp=in_one_day)
    stream += 'WRONG_ISSUER_ASSERTION = "%s"\n' % \
            get_assertion('alexis@loadtest.local', exp=in_one_day)

    stream += 'WRONG_EMAIL_HOST_ASSERTION = "%s"\n' % \
            get_assertion('alexis@mozilla.com', issuer='loadtest.local',
                          exp=in_one_day)
    stream += 'EXPIRED_TOKEN = "%s"\n' % \
            get_assertion('alexis@loadtest.local', issuer='loadtest.local',
                          exp=int(time.time() - 60) * 1000)

    return stream


if __name__ == '__main__':
    with open('assertions.py', 'w') as f:
        f.write(generate_assertions())
