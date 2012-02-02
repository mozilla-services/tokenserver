import os
from setuptools import setup, find_packages


requires = ['cornice', 'pyvep']


setup(name='tokenserver',
      version='0.1',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires)
