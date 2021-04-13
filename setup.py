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
        'Sphinx~=3.5.3',
        'sphinx-autodoc-typehints',
        'sphinx-copybutton',
        'sphinx-rtd-theme~=0.5.2',
        'sphinxcontrib-apidoc',
    ],
    # Packages used for testing both locally and in CI jobs
    'test': [
        'black==20.8b1',
        'flake8',
        'flake8-comprehensions',
        'flake8-polyfill',
        'isort',
        'pre-commit',
        'psutil',
        'pytest>=5.0',
        'pytest-cov>=2.11',
        'pytest-xdist',
        'radon',
        'requests-mock>=1.8',
        'timeout-decorator',
    ],
}
# All development/testing packages combined
extras_require['dev'] = list(chain.from_iterable(extras_require.values()))


setup(
    name='requests-cache',
    packages=find_packages(exclude=['tests*']),
    version=__version__,
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/reclosedev/requests-cache',
    install_requires=['itsdangerous', 'requests>=2.0.0', 'url-normalize>=1.4'],
    extras_require=extras_require,
    python_requires='>=3.6',
    include_package_data=True,
)
