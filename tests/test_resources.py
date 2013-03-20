"""
Unit tests for :mod:`manwe.resources`.
"""


import datetime

from mock import Mock
from nose.tools import *

from manwe import resources, session


class TestResources():
    """
    Test :mod:`manwe.resources`.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_sample(self):
        """
        Read field values from a sample with correct types.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user_uri': '/users/8',
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        assert_equal(sample.name, 'test sample')
        assert_equal(sample.pool_size, 5)
        assert_equal(sample.public, False)
        assert_equal(sample.added, datetime.datetime(2012, 11, 23, 10, 55, 12))

    def test_edit_sample(self):
        """
        Edit field values of a sample.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user_uri': '/users/8',
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        sample.name = 'edited test sample'

    @raises(AttributeError)
    def test_edit_immutable_sample(self):
        """
        Edit immutable field values of a sample.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user_uri': '/users/8',
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        sample.uri = '/some/uri/88'

    def test_edit_save_sample(self):
        """
        Save edited field values of a sample.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user_uri': '/users/8',
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        sample.name = 'edited test sample'
        sample.pool_size = 3
        assert sample.dirty
        sample.save()
        self.session.request.assert_called_once_with(
            '/samples/3', method='PATCH', data={'name': 'edited test sample',
                                                'pool_size': 3})
        assert not sample.dirty
