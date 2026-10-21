#!/usr/bin/env python3

import setuptools

exec(compile(open('_/version.py').read(),'version.py','exec'))

setuptools.setup(
    name                 = 'underscorepy',
    author               = __author__,
    author_email         = __email__,
    version              = __version__,
    license              = __license__,
    url                  = 'https://shaw.cx/_.py',
    description          = '_.py library',
    long_description     = open('README.md').read(),
    packages             = setuptools.find_packages(),
    include_package_data = True,
    zip_safe             = False,
    python_requires      = '>=3.10',
    install_requires = [
        'tornado',
        'sqlalchemy[asyncio]>=2.0',
        ],
    extras_require = {
        'postgres' : ['asyncpg'],
        'sqlite'   : ['aiosqlite'],
        'redis'    : ['redis>=4.2'],
        'protobuf' : ['protobuf'],
        'ldap'     : ['python-ldap'],
        'test'     : ['pytest', 'aiosqlite'],
        },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.10',
        ]
    )
