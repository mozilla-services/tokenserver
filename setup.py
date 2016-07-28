# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup, find_packages


requires = ['cornice', 'mozsvc>=0.8', 'PyBrowserID', 'testfixtures']


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
      tests_require=requires,
      test_suite='tokenserver.tests')
