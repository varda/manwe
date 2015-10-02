# -*- coding: utf-8 -*-
"""
Manwë configuration object.


.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import os

import flask.config

from . import default_config


class AttributeDictMixin(object):
    """
    Augment classes with a Mapping interface by adding attribute access.

    Taken from `Celery <http://www.celeryproject.org/>`_
    (`celery.datastructures.AttributeDictMixin`).
    """
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(
                '{0!r} object has no attribute {1!r}'.format(
                    type(self).__name__, k))

    def __setattr__(self, key, value):
        self[key] = value


class Config(flask.config.Config, AttributeDictMixin):
    """
    Dictionary with some extra ways to fill it from files or special
    dictionaries (see `flask.config.Config`) and attribute access.

    Initialized with :mod:`manwe.default_config`.
    """
    def __init__(self):
        # We fix the root_path argument to the current working directory.
        super(Config, self).__init__(os.getcwd())
        self.from_object(default_config)
