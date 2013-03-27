# -*- coding: utf-8 -*-
import sys
from setuptools import setup

if sys.version_info < (2, 7):
    raise Exception('Manwë requires Python 2.7 or higher.')

# Todo: How does this play with pip freeze requirement files?
requires = []

import manwe as distmeta

setup(
    name='manwe',
    version=distmeta.__version__,
    description='A Python client library and command line interface to the '
    'Varda database for genomic variation frequencies',
    long_description=distmeta.__doc__,
    author=distmeta.__author__,
    author_email=distmeta.__contact__,
    url=distmeta.__homepage__,
    license='MIT License',
    platforms=['any'],
    packages=['manwe'],
    requires=requires,
    entry_points = {
        'console_scripts': ['manwe = manwe.commands:main']
        },
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering',
        ],
    keywords='bioinformatics'
)
