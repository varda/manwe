# -*- coding: utf-8 -*-
"""
Manwë, a Python client library and command line interface to the Varda
database for genomic variation frequencies.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from .session import Session


# We follow a versioning scheme compatible with setuptools [1] where the
# package version is always that of the upcoming release (and not that of the
# previous release), post-fixed with ``.dev``. Only in a release commit, the
# ``.dev`` is removed (and added again in the next commit).
#
# Note that this scheme is not 100% compatible with SemVer [2] which would
# require ``-dev`` instead of ``.dev``.
#
# [1] http://peak.telecommunity.com/DevCenter/setuptools#specifying-your-project-s-version
# [2] http://semver.org/


__version_info__ = ('1', '2', '1')
__date__ = '2 Oct 2015'


__version__ = '.'.join(__version_info__)
__author__ = 'Martijn Vermaat'
__contact__ = 'martijn@vermaat.name'
__homepage__ = 'https://github.com/varda/manwe'


# Set default logging handler to avoid "No handler found" warnings.
import logging
try:
    # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
logging.getLogger('manwe').addHandler(NullHandler())
