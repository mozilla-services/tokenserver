# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup, find_packages


requires = ['cornice', 'mozsvc', 'powerhose', 'circus', 'wimms', 'PyBrowserID',
            'pylibmc', 'metlog-py']

setup(name='tokenserver',
      version='0.7',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      entry_points="""\
      [paste.app_factory]
      main = tokenserver:main
      [console_scripts]
      generate-secret = tokenserver.scripts:generate_secret
      display-secrets = tokenserver.scripts:display_secrets
      """,
      install_requires=requires,
      tests_require=requires,
      test_suite='tokenserver.tests')
