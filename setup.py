#!/usr/bin/env python
from itertools import chain
from setuptools import find_packages, setup

from requests_cache import __version__

extras_require = {
    # Packages used for CI jobs
    'build': ['coveralls', 'twine', 'wheel'],
    # Packages for all supported backends + features
    'backends': ['boto3', 'pymongo', 'redis'],
    # Packages used for documentation builds
    'docs': [
        'm2r2',
        'Sphinx~=3.5.1',
        'sphinx-autodoc-typehints',
        'sphinx-copybutton',
        'sphinx-rtd-theme',
        'sphinxcontrib-apidoc',
    ],
    # Packages used for testing both locally and in CI jobs
    'test': [
        'black==20.8b1',
        'flake8',
        'isort',
        'pre-commit',
        'pytest>=5.0',
        'pytest-cov>=2.11',
        'requests-mock>=1.8',
    ],
}
# All development/testing packages combined
extras_require['dev'] = list(chain.from_iterable(extras_require.values()))


setup(
    name='requests-cache',
    packages=find_packages(),
    version=__version__,
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/reclosedev/requests-cache',
    install_requires=['itsdangerous', 'requests>=2.0.0', 'url-normalize>=1.4'],
    extras_require=extras_require,
    include_package_data=True,
)
