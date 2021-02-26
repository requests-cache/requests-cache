#!/usr/bin/env python
from setuptools import find_packages, setup

setup(
    name='requests-cache',
    packages=find_packages(),
    version='0.5.2',
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/reclosedev/requests-cache',
    install_requires=['requests>=2.0.0'],
    include_package_data=True,
)
