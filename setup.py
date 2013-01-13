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
    name='requests-cache',
    packages=['requests_cache', 'requests_cache.backends'],
    version='0.2.1',
    description='Persistent cache for requests library',
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/reclosedev/requests-cache',
    install_requires=['requests==0.14.2'],
    keywords=['requests', 'cache', 'persistence'],
    license='BSD License',
    include_package_data=True,
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    long_description=open('README.rst').read() + '\n\n' +
                     open('HISTORY.rst').read(),
)
