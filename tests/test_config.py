"""
Unit tests for :mod:`manwe.config`.
"""


import os
import tempfile

from mock import patch
from nose.tools import *

from manwe import config


class TestConfig():
    """
    Test :mod:`manwe.config`.
    """
    @raises(AttributeError)
    def test_nonexisting_values(self):
        """
        We only have the known config values.
        """
        c = config.Config()
        c.bladiebla

    def test_default_values(self):
        """
        With no config files, we are left with default values.
        """
        with patch.object(os.path, 'isfile') as mock_isfile:
            mock_isfile.return_value = False
            c = config.Config()
        assert_equal(c.user, None)
        assert_equal(c.poll_sleep, config.DEFAULT_POLL_SLEEP)

    def test_from_file(self):
        """
        We can read values from a config file we supply.
        """
        _, path = tempfile.mkstemp()
        try:
            with open(path, 'w') as temp_config:
                temp_config.write('user = pietje test\n')
                temp_config.write('poll_sleep = 88\n')
            c = config.Config(path)
            assert_equal(c.user, 'pietje test')
            assert_equal(c.poll_sleep, 88)
        finally:
            os.unlink(path)

    def test_overwrite_order(self):
        """
        Values are used from sources in this order:

        1. Constructor argument values.
        2. Constructor filename argument.
        3. Config files in standard locations (not tested here).
        4. Default values.
        """
        _, path = tempfile.mkstemp()
        try:
            with open(path, 'w') as temp_config:
                temp_config.write('user = pietje test\n')
                temp_config.write('poll_sleep = 88\n')
            c = config.Config(path, user='karel test')
            assert_equal(c.user, 'karel test')
            assert_equal(c.poll_sleep, 88)
            assert_equal(c.max_polls, config.DEFAULT_MAX_POLLS)
        finally:
            os.unlink(path)

    def test_value_type(self):
        """
        All configuration values have a specific type.
        """
        _, path = tempfile.mkstemp()
        try:
            with open(path, 'w') as temp_config:
                temp_config.write('api_root = http://some.loc:88/api\n')
                temp_config.write('user = pietje test\n')
                temp_config.write('poll_sleep = 88\n')
            c = config.Config(path, max_polls='78')
            assert_equal(type(c.api_root), str)
            assert_equal(type(c.user), str)
            assert_equal(type(c.poll_sleep), int)
            assert_equal(type(c.max_polls), int)
        finally:
            os.unlink(path)
