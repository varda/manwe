# -*- coding: utf-8 -*-
"""
Manwë configuration.

By default, configuration values are read from two locations, in this order:

1. ``/etc/manwe/config``
2. ``$XDG_CONFIG_HOME/manwe/config``

If both files exist, values defined in the second overwrite values defined in
the first.

An exception to this system is when the optional `filename` argument is passed
to :class:`Config`. In that case, the locations listed above are ignored and
the configuration is read from `filename`.

Additionally, any keyword arguments passed to :class:`Config` other than
`filename` will overwrite values read from a file.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


# Todo: Drop configobj dependency, probably use something like ConfigParser
#     from the standard library. I think configobj is our only dependency
#     keeping us from running on Python 3.


import os
from configobj import ConfigObj


DEFAULT_API_ROOT = 'http://127.0.0.1:5000'
DEFAULT_POLL_SLEEP = 5
DEFAULT_MAX_POLLS = 50000

SYSTEM_CONFIGURATION = '/etc/manwe/config'
USER_CONFIGURATION = os.path.join(
    os.environ.get('XDG_CONFIG_HOME', None)
    or os.path.join(os.path.expanduser('~'), '.config'),
    'manwe', 'config')


class ConfigurationError(Exception):
    """
    Raised when a configuration file cannot be read.
    """
    pass


class Config(object):
    """
    Read the configuration file and provide access to its values.
    """
    def __init__(self, filename=None, **values):
        """
        Initialise the class with variables read from the configuration
        file.

        By default, configuration values are read from two locations, in this
        order:

        1. `SYSTEM_CONFIGURATION`
        2. `USER_CONFIGURATION`

        If both files exist, values defined in the second overwrite values
        defined in the first.

        An exception to this system is when the optional `filename` argument
        is set. In that case, the locations listed above are ignored and the
        configuration is read from `filename`.

        Additionally, any keyword arguments passed to :class:`Config` other
        than `filename` will overwrite values read from a file.

        :arg filename: Optional filename to read configuration from. If
            present, this overrides automatic detection of configuration file
            location.
        :type filename: str

        :raise ConfigurationError: If configuration could not be read.
        """
        config = {}

        if filename:
            config = self._load_config(filename)
        else:
            if os.path.isfile(SYSTEM_CONFIGURATION):
                config = self._load_config(SYSTEM_CONFIGURATION)
            if os.path.isfile(USER_CONFIGURATION):
                user_config = self._load_config(USER_CONFIGURATION)
                if config:
                    config.merge(user_config)
                else:
                    config = user_config

        # Any not-None keyword arguments overwrite existing values.
        overwrite = {key: value for key, value in values.items()
                     if value is not None}
        if config:
            config.merge(overwrite)
        else:
            config = ConfigObj(overwrite)

        self.api_root = config.get('api_root', DEFAULT_API_ROOT)
        self.token = config.get('token')
        self.poll_sleep = int(config.get('poll_sleep', DEFAULT_POLL_SLEEP))
        self.max_polls = int(config.get('max_polls', DEFAULT_MAX_POLLS))

    def _load_config(self, filename):
        """
        Create a `ConfigObj` instance from the configuration in `filename`.
        """
        try:
            return ConfigObj(filename)
        except IOError:
            raise ConfigurationError('Could not open configuration file "%s"'
                                     % filename)
        except SyntaxError:
            raise ConfigurationError('Could not parse configuration file "%s"'
                                     % filename)

    def get(self, key, default=None):
        """
        Return the value for `key` if `key` is in the configuration, else
        `default`. If `default` is not given, it defaults to ``None``.
        """
        try:
            return getattr(self, key)
        except AttributeError:
            return default
