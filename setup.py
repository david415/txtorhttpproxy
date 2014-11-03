#!/usr/bin/env python

from setuptools import setup

__version__ = '0.0.1'
__author__ = 'David Stainton'
__contact__ = 'dstainton415@gmail.com'
__url__ = 'https://github.com/david415/txtorhttpproxy'
__license__ = 'GPL'
__copyright__ = 'Copyright 2014'

setup(
    name='txtorhttpproxy',
    description='Tor-friendly Twisted http proxy classes',
    version = __version__,
    long_description = open('README.rst', 'r').read(),
    keywords = ['python', 'twisted', 'tor', 'twisted endpoint',
                'tor socks client', 'tor http proxy', 'http proxy'],

    classifiers=['Framework :: Twisted',
                 'Development Status :: 3 - Alpha',
                 'Intended Audience :: Developers',
                 'Operating System :: OS Independent',
                 'License :: OSI Approved :: GPL License',
                 'Operating System :: POSIX :: Linux',
                 'Operating System :: Unix',
                 'Programming Language :: Python :: 2.6',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 2 :: Only',
                 'Topic :: Software Development :: Libraries :: Python Modules',
                 'Topic :: Internet',
                 'Topic :: Security'],
    author = __author__,
    author_email = __contact__,
    url = __url__,
    license = __license__,
    install_requires=open('requirements.txt', 'rb').read().split(),
    packages=['txtorhttpproxy'],
    scripts=['bin/torhttpproxy']
)
