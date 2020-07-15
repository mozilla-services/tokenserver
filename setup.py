# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup, find_packages


def load_req(filename):
    """Load a pip style requirement file."""
    reqs = []
    with open(filename, "r") as file:
        for line in file.readlines():
            line = line.strip()
            if line.startswith("-r"):
                content = load_req(line.split(' ')[1])
                reqs.extend(content)
                continue
            reqs.append(line)
    return reqs


requires = load_req("requirements.txt")
tests_require = load_req("dev-requirements.txt")


setup(name='tokenserver',
      version='1.5.8',
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
