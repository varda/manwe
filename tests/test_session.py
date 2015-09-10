"""
Unit tests for :mod:`manwe.session`.
"""


import utils


class TestSession(utils.TestEnvironment):
    def test_get_user(self):
        """
        Get a user.
        """
        admin_uri = self.uri_for_user(name='Administrator')
        assert self.session.user(admin_uri).name == 'Administrator'

    def test_create_sample(self):
        """
        Create a sample.
        """
        sample = self.session.create_sample('test sample', pool_size=5, public=True)
        assert sample.name == 'test sample'

        sample_uri = self.uri_for_sample(name='test sample')
        assert sample.uri == sample_uri

    def test_create_data_source(self):
        """
        Create a data source.
        """
        data_source = self.session.create_data_source('test data source', 'vcf', data='test_data')

        data_source_uri = self.uri_for_data_source(name='test data source')
        assert data_source.uri == data_source_uri
