# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import unittest
from tempfile import mkstemp
import os
import time

from tokenserver.util import generate_secret
from mozsvc.secrets import Secrets


class TestUtil(unittest.TestCase):

    def test_secret_append(self):

        fd, filename = mkstemp()
        os.close(fd)
        try:
            generate_secret(filename, 'node')
            time.sleep(1.1)
            generate_secret(filename, 'node')
            secrets = Secrets(filename)
            self.assertEqual(len(secrets.get('node')), 2)
        finally:
            os.remove(filename)
