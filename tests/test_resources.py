"""
Unit tests for :mod:`manwe.resources`.
"""


import datetime

from mock import Mock
from nose.tools import *
import requests

from manwe import resources, session


class TestAnnotation():
    """
    Test :class:`manwe.resources.Annotation` and :class:`manwe.resources.AnnotationCollection`
    classes.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_annotation(self):
        """
        Read field values from an annotation with correct types.
        """
        fields = dict(uri='/annotations/3',
                      original_data_source_uri='/data_sources/4',
                      annotated_data_source_uri='/data_sources/6',
                      written=True)

        annotation = resources.Annotation(self.session, fields)
        assert_equal(annotation.uri, '/annotations/3')
        assert_equal(annotation.written, True)


class TestCoverage():
    """
    Test :class:`manwe.resources.Coverage` and :class:`manwe.resources.CoverageCollection`
    classes.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_coverage(self):
        """
        Read field values from a coverage with correct types.
        """
        fields = dict(uri='/coverages/8',
                      sample_uri='/samples/3',
                      data_source_uri='/data_sources/1',
                      imported=True)

        coverage = resources.Coverage(self.session, fields)
        assert_equal(coverage.uri, '/coverages/8')
        assert_equal(coverage.imported, True)


class TestDataSource():
    """
    Test :class:`manwe.resources.DataSource` and :class:`manwe.resources.DataSourceCollection`
    classes.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_data_source(self):
        """
        Read field values from a data source with correct types.
        """
        fields = dict(uri='/data_sources/4',
                      name='test',
                      user_uri='/users/2',
                      data_uri='/data_sources/4/data',
                      filetype='test',
                      gzipped=True,
                      added='2012-11-23T10:55:12')

        data_source = resources.DataSource(self.session, fields)
        assert_equal(data_source.uri, '/data_sources/4')
        assert_equal(data_source.gzipped, True)
        assert_equal(data_source.added, datetime.datetime(2012, 11, 23, 10, 55, 12))


class TestSample():
    """
    Test :class:`manwe.resources.Sample` and :class:`manwe.resources.SampleCollection`
    classes.
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
                   'active': True,
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        assert_equal(sample.name, 'test sample')
        assert_equal(sample.pool_size, 5)
        assert_equal(sample.public, False)
        assert_equal(sample.added, datetime.datetime(2012, 11, 23, 10, 55, 12))

    def test_read_sample_user(self):
        """
        Read user from a sample.
        """
        self.session.user.return_value = 'mock user'

        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user_uri': '/users/8',
                   'active': True,
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        user = sample.user
        self.session.user.assert_called_once_with('/users/8')
        assert_equal(user, 'mock user')

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
                   'active': True,
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(self.session, fields)
        assert not sample.dirty
        sample.name = 'edited test sample'
        assert sample.dirty

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
                   'active': True,
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
                   'active': True,
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
                    'active': True,
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


class TestUser():
    """
    Test :class:`manwe.resources.User` and :class:`manwe.resources.UserCollection`
    classes.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_user(self):
        """
        Read field values from a user with correct types.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(self.session, fields)
        assert_equal(user.uri, '/users/4')
        assert_equal(user.roles, {'importer'})
        assert_equal(user.added, datetime.datetime(2012, 11, 23, 10, 55, 12))

    def test_edit_user(self):
        """
        Edit field values of a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(self.session, fields)
        assert not user.dirty
        user.name = 'edited test user'
        assert user.dirty

    @raises(AttributeError)
    def test_add_user_role_directly(self):
        """
        Try to add role to a user directly.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(self.session, fields)
        user.roles.add('annotator')

    def test_add_user_role(self):
        """
        Add role to a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(self.session, fields)
        assert not user.dirty
        user.add_role('annotator')
        assert user.dirty
        assert_equal(user.roles, {'importer', 'annotator'})

    def test_remove_user_role(self):
        """
        Remove role from a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(self.session, fields)
        assert not user.dirty
        user.remove_role('importer')
        assert user.dirty
        assert_equal(user.roles, set())

    def test_edit_user_role(self):
        """
        Edit roles field values of a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(self.session, fields)
        assert not user.dirty
        user.roles = {'importer', 'annotator'}
        assert user.dirty
        assert_equal(user.roles, {'importer', 'annotator'})


class TestVariant():
    """
    Test :class:`manwe.resources.Variant` and :class:`manwe.resources.VariantCollection`
    classes.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_variant(self):
        """
        Read field values from a variant with correct types.
        """
        fields = dict(uri='/variants/3',
                      chromosome='chr5',
                      position=45353,
                      reference='AT',
                      observed='TA',
                      global_frequency=(0.4, [0.3, 0.1]),
                      sample_frequency=[(0.4, [0.3, 0.1]), (0.4, [0.3, 0.1])])

        variant = resources.Variant(self.session, fields)
        assert_equal(variant.uri, '/variants/3')
        assert_equal(variant.position, 45353)
        assert_equal(variant.global_frequency, (0.4, [0.3, 0.1]))
        assert_equal(variant.sample_frequency, [(0.4, [0.3, 0.1]), (0.4, [0.3, 0.1])])


class TestVariation():
    """
    Test :class:`manwe.resources.Variation` and :class:`manwe.resources.VariationCollection`
    classes.
    """
    def setup(self):
        self.session = Mock(session.Session)

    def test_read_variation(self):
        """
        Read field values from a variation with correct types.
        """
        fields = dict(uri='/variations/23',
                      sample_uri='/samples/3',
                      data_source_uri='/data_sources/6',
                      imported=True)

        variation = resources.Variation(self.session, fields)
        assert_equal(variation.uri, '/variations/23')
        assert_equal(variation.imported, True)
