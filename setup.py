# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup, find_packages


requires = [
    'boto',
    'cornice',
    'hawkauthlib',
    'mozsvc',
    'PyBrowserID',
    'pyramid < 1.8',  # To keep Py26 support.
    'SQLAlchemy',
    'testfixtures',
    'tokenlib',
    'umemcache',
]

tests_require = [
    'mock',
    'nose',
    'unittest2',
    'webtest < 2.0.23',  # To keep Py26 support.
]


setup(name='tokenserver',
      version='1.2.23',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      entry_points="""\
      [paste.app_factory]
      main = tokenserver:main
      """,
      install_requires=requires,
      tests_require=tests_require,
      test_suite='tokenserver.tests')
