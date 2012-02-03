import os
from setuptools import setup, find_packages


requires = ['cornice', 'repoze.who.plugins.vepauth', 'mozsvc']


setup(name='tokenserver',
      version='0.1',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      entry_points = """\
      [paste.app_factory]
      main = tokenserver:main
      """,
      install_requires=requires)
