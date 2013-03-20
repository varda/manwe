"""
Unit tests for :mod:`manwe.resources`.
"""


import datetime

from mock import Mock
from nose.tools import *
import requests

from manwe import resources, session


class TestResources():
    """
    Test :mod:`manwe.resources`.
    """
    def setup(self):
        self.session = Mock(session.Session, uris={'samples': '/samples'})

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

    def test_sample_collection(self):
        """
        Iterate over the samples in a sample collection.
        """
        def create_sample(i):
            return {'name': 'test sample %i' % i,
                    'pool_size': 5,
                    'coverage_profile': True,
                    'public': False,
                    'uri': '/samples/%i' % i,
                    'user_uri': '/users/8',
                    'added': '2012-11-23T10:55:12'}
        def create_mock_response(start, end, total):
            samples = [create_sample(i) for i in range(start, end)]
            mock_response = Mock(requests.Response)
            mock_response.json.return_value = {'samples': samples}
            mock_response.headers = {'Content-Range': 'items %d-%d/%d' % (start, end, total)}
            return mock_response

        # Total number of samples in our collection is 2 times the cache size
        # plus 3.
        total = 2 * resources.COLLECTION_CACHE_SIZE + 3
        pages = [(1, resources.COLLECTION_CACHE_SIZE + 1),
                 (resources.COLLECTION_CACHE_SIZE + 1, 2 * resources.COLLECTION_CACHE_SIZE + 1),
                 (2 * resources.COLLECTION_CACHE_SIZE + 1, 2 * resources.COLLECTION_CACHE_SIZE + 4)]
        self.session.get.side_effect = (create_mock_response(start, end, total)
                                        for start, end in pages)

        samples = resources.SampleCollection(self.session)
        assert_equal(samples.size, total)
        sample_list = list(samples)
        assert_equal(len(sample_list), total)
        assert_equal(sample_list[0].name, 'test sample 1')
        assert_equal(sample_list[-1].name, 'test sample %i' % total)
