# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup, find_packages


requires = [
    'alembic',
    'boto',
    'cornice',
    'hawkauthlib',
    'mozsvc',
    'Paste',
    'PyBrowserID',
    'PyFxA',
    'PyMySQL',
    'pymysql_sa',
    'SQLAlchemy',
    'testfixtures',
    'tokenlib',
]

tests_require = [
    'mock',
    'nose',
    'unittest2',
    'webtest',
]


setup(name='tokenserver',
      version='1.3.1',
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
