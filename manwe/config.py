"""
Manwë configuration.

All communication with this module should be done by using the get function
which returns a configuration value, given a name.

Reading the configuration file is implemented lazily and as such done upon the
first call to the get function.

Configuration values are read from two locations, in this order:
1) /etc/manwe/config
2) $XDG_CONFIG_HOME/manwe/config

If both files exist, values defined in the second overwrite values defined in
the first.
"""


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
    def __init__(self, filename=None):
        """
        Initialise the class with variables read from the configuration
        file.

        Configuration values are read from two locations, in this order:
        - SYSTEM_CONFIGURATION
        - USER_CONFIGURATION

        If both files exist, values defined in the second overwrite values
        defined in the first.

        An exception to this system is when the optional `filename` argument
        is set. In that case, the locations listed above are ignored and the
        configuration is read from `filename`.

        :arg filename: Optional filename to read configuration from. If
            present, this overrides automatic detection of configuration file
            location.
        :type filename: str

        :raise ConfigurationError: If configuration could not be read.
        """
        config = None

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

        if not config:
            raise ConfigurationError('Could not locate configuration')

        self.api_root = config.get('api_root', DEFAULT_API_ROOT)
        self.user = config.get('user')
        self.password = config.get('password')
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
