#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import glob
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


if sys.argv[-1] == 'test':
    os.chdir('tests')
    for test in glob.glob('*.py'):
        os.system('python %s' % test)
    sys.exit()

setup(
    name="requests-cache",
    packages=["requests_cache", "requests_cache.backends"],
    version="0.1.0",
    description="Persistent cache for requests library",
    author="Roman Haritonov",
    author_email="reclosedev@gmail.com",
    url="https://bitbucket.org/reclosedev/requsts-cache",
    install_requires=['requests'],
    keywords=["requests", "cache", "persistence"],
    license="BSD License",
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: BSD License",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
    long_description=open('README').read(),
)
