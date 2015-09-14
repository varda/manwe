# -*- coding: utf-8 -*-
import os
from setuptools import setup
import sys

if sys.version_info < (2, 7):
    raise Exception('Manwë requires Python 2.7 or higher.')

install_requires = ['python-dateutil', 'requests-toolbelt', 'Flask']

try:
    with open('README.rst') as readme:
        long_description = readme.read()
except IOError:
    long_description = 'See https://pypi.python.org/pypi/manwe'

# This is quite the hack, but we don't want to import our package from here
# since that's recipe for disaster (it might have some uninstalled
# dependencies, or we might import another already installed version).
distmeta = {}
for line in open(os.path.join('manwe', '__init__.py')):
    try:
        field, value = (x.strip() for x in line.split('='))
    except ValueError:
        continue
    if field == '__version_info__':
        value = value.strip('[]()')
        value = '.'.join(x.strip(' \'"') for x in value.split(','))
    else:
        value = value.strip('\'"')
    distmeta[field] = value

setup(
    name='manwe',
    version=distmeta['__version_info__'],
    description='A Python client library and command line interface to the '
    'Varda database for genomic variation frequencies',
    long_description=long_description,
    author=distmeta['__author__'],
    author_email=distmeta['__contact__'],
    url=distmeta['__homepage__'],
    license='MIT License',
    platforms=['any'],
    packages=['manwe'],
    install_requires=install_requires,
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
