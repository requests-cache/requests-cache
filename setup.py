#!/usr/bin/env python
from itertools import chain
from setuptools import find_packages, setup

extras_require = {
    # Packages used for CI jobs
    'build': ['coveralls', 'twine', 'wheel'],
    # Packages for all supported backends
    'backends': ['boto3', 'pymongo', 'redis'],
    # Packages used for testing both locally and in CI jobs
    'test': [
        'black==20.8b1',
        'flake8',
        'isort',
        'pre-commit',
        'pytest>=5.0',
        'pytest-cov',
    ],
}
# All development/testing packages combined
extras_require['dev'] = list(chain.from_iterable(extras_require.values()))

setup(
    name='requests-cache',
    packages=find_packages(),
    version='0.6.0',
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/reclosedev/requests-cache',
    install_requires=['requests>=2.0.0'],
    extras_require=extras_require,
    include_package_data=True,
)
