"""
Unit tests for :mod:`manwe.resources`.
"""


import datetime

import pytest
from varda import db
from varda.models import Sample, User

from manwe import resources

import utils


class TestAnnotation(object):
    def test_read_annotation(self):
        """
        Read field values from an annotation with correct types.
        """
        fields = dict(uri='/annotations/3',
                      original_data_source={'uri': '/data_sources/4'},
                      annotated_data_source={'uri': '/data_sources/6'})

        annotation = resources.Annotation(None, fields)
        assert annotation.uri == '/annotations/3'


class TestCoverage(object):
    def test_read_coverage(self):
        """
        Read field values from a coverage with correct types.
        """
        fields = dict(uri='/coverages/8',
                      sample={'uri': '/samples/3'},
                      data_source={'uri': '/data_sources/1'})

        coverage = resources.Coverage(None, fields)
        assert coverage.uri == '/coverages/8'


class TestDataSource(object):
    def test_read_data_source(self):
        """
        Read field values from a data source with correct types.
        """
        fields = dict(uri='/data_sources/4',
                      name='test',
                      user={'uri': '/users/2'},
                      data={'uri': '/data_sources/4/data'},
                      filetype='test',
                      gzipped=True,
                      added='2012-11-23T10:55:12')

        data_source = resources.DataSource(None, fields)
        assert data_source.uri == '/data_sources/4'
        assert data_source.gzipped
        assert data_source.added == datetime.datetime(2012, 11, 23, 10, 55, 12)


class TestSample(object):
    def test_read_sample(self):
        """
        Read field values from a sample with correct types.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user': {'uri': '/users/8'},
                   'active': True,
                   'notes': 'Some test notes',
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(None, fields)
        assert sample.name == 'test sample'
        assert sample.pool_size == 5
        assert not sample.public
        assert sample.notes == 'Some test notes'
        assert sample.added == datetime.datetime(2012, 11, 23, 10, 55, 12)
        assert str(sample) == sample.uri

    def test_read_sample_user(self):
        """
        Read user from a sample.
        """
        class MockSession(object):
            def user(self, uri):
                return 'mock user'
        s = MockSession()

        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user': {'uri': '/users/8'},
                   'active': True,
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(s, fields)
        user = sample.user
        assert user == 'mock user'

    def test_edit_sample(self):
        """
        Edit field values of a sample.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user': {'uri': '/users/8'},
                   'active': True,
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(None, fields)
        assert not sample.dirty
        sample.name = 'edited test sample'
        assert sample.dirty

    def test_edit_immutable_sample(self):
        """
        Edit immutable field values of a sample.
        """
        fields =  {'name': 'test sample',
                   'pool_size': 5,
                   'coverage_profile': True,
                   'public': False,
                   'uri': '/samples/3',
                   'user': {'uri': '/users/8'},
                   'active': True,
                   'added': '2012-11-23T10:55:12'}
        sample = resources.Sample(None, fields)
        with pytest.raises(AttributeError):
            sample.uri = '/some/uri/88'


class TestSampleCollection(utils.TestEnvironment):
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
                    'user': {'uri': '/users/8'},
                    'active': True,
                    'added': '2012-11-23T10:55:12'}

        # Total number of samples in our collection is 2 times the cache size
        # plus 3.
        total = resources.COLLECTION_CACHE_SIZE * 2 + 3

        user = User.query.first()
        for i in range(total):
            sample = Sample(user, 'test sample %d' % (i + 1))
            db.session.add(sample)
        db.session.commit()

        samples = resources.SampleCollection(self.session)
        assert samples.size == total
        sample_list = list(samples)
        assert len(sample_list) == total
        assert sample_list[0].name == 'test sample 1'
        assert sample_list[-1].name == 'test sample %i' % total

    def test_sample_collection_user(self):
        """
        Request a sample collection for a user.
        """
        user_uri = self.uri_for_user()
        user = self.session.user(user_uri)

        samples = resources.SampleCollection(self.session, user=user)
        assert samples.user == user


class TestUser(object):
    def test_read_user(self):
        """
        Read field values from a user with correct types.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      email='test@test.com',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(None, fields)
        assert user.uri == '/users/4'
        assert user.email == 'test@test.com'
        assert user.roles == {'importer'}
        assert user.added == datetime.datetime(2012, 11, 23, 10, 55, 12)

    def test_edit_user(self):
        """
        Edit field values of a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(None, fields)
        assert not user.dirty
        user.name = 'edited test user'
        assert user.dirty

    def test_add_user_role_directly(self):
        """
        Try to add role to a user directly.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(None, fields)
        with pytest.raises(AttributeError):
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

        user = resources.User(None, fields)
        assert not user.dirty
        user.add_role('annotator')
        assert user.dirty
        assert user.roles == {'importer', 'annotator'}

    def test_remove_user_role(self):
        """
        Remove role from a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(None, fields)
        assert not user.dirty
        user.remove_role('importer')
        assert user.dirty
        assert user.roles == set()

    def test_edit_user_role(self):
        """
        Edit roles field values of a user.
        """
        fields = dict(uri='/users/4',
                      name='test',
                      login='test',
                      roles=['importer'],
                      added='2012-11-23T10:55:12')

        user = resources.User(None, fields)
        assert not user.dirty
        user.roles = {'importer', 'annotator'}
        assert user.dirty
        assert user.roles == {'importer', 'annotator'}

    def test_user_eq(self):
        """
        Compare two equal users.
        """
        fields_a = dict(uri='/users/4', login='test')
        fields_b = dict(uri='/users/4', login='test')

        user_a = resources.User(None, fields_a)
        user_b = resources.User(None, fields_b)

        assert user_a == user_b

    def test_user_eq_by_uri(self):
        """
        Compare two users with equal URIs.
        """
        fields_a = dict(uri='/users/4', login='test a')
        fields_b = dict(uri='/users/4', login='test b')

        user_a = resources.User(None, fields_a)
        user_b = resources.User(None, fields_b)

        assert user_a == user_b

    def test_user_neq(self):
        """
        Compare two inequal users.
        """
        fields_a = dict(uri='/users/4', login='test a')
        fields_b = dict(uri='/users/6', login='test b')

        user_a = resources.User(None, fields_a)
        user_b = resources.User(None, fields_b)

        assert user_a != user_b

    def test_user_neq_by_uri(self):
        """
        Compare two users with inequal URIs.
        """
        fields_a = dict(uri='/users/4', login='test a')
        fields_b = dict(uri='/users/6', login='test a')

        user_a = resources.User(None, fields_a)
        user_b = resources.User(None, fields_b)

        assert user_a != user_b


class TestVariant(object):
    def test_read_variant(self):
        """
        Read field values from a variant with correct types.
        """
        fields = dict(uri='/variants/3',
                      chromosome='chr5',
                      position=45353,
                      reference='AT',
                      observed='TA')

        variant = resources.Variant(None, fields)
        assert variant.uri == '/variants/3'
        assert variant.chromosome == 'chr5'
        assert variant.position == 45353
        assert variant.reference == 'AT'
        assert variant.observed == 'TA'


class TestVariation(object):
    def test_read_variation(self):
        """
        Read field values from a variation with correct types.
        """
        fields = dict(uri='/variations/23',
                      sample={'uri': '/samples/3'},
                      data_source={'uri': '/data_sources/6'})

        variation = resources.Variation(None, fields)
        assert variation.uri == '/variations/23'
