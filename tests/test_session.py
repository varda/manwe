"""
Unit tests for :mod:`manwe.session`.
"""


import pytest
import varda
import varda.models

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

    def test_samples_by_user(self):
        """
        Filter sample collection by user.
        """
        a = varda.models.User('User A', 'a')
        b = varda.models.User('User B', 'b')

        samples_a = [varda.models.Sample(a, 'Sample A %d' % i)
                     for i in range(50)]
        samples_b = [varda.models.Sample(b, 'Sample B %d' % i)
                     for i in range(50)]

        varda.db.session.add_all(samples_a + samples_b)
        varda.db.session.commit()

        admin = self.session.user(self.uri_for_user(name='Administrator'))
        a = self.session.user(self.uri_for_user(name='User A'))
        b = self.session.user(self.uri_for_user(name='User B'))

        samples = self.session.samples()
        assert samples.size == 100

        samples_a = self.session.samples(user=a)
        assert samples_a.size == 50
        assert samples_a.user == a
        assert next(samples_a).user == a
        assert next(samples_a).name.startswith('Sample A ')

        samples_b = self.session.samples(user=b)
        assert samples_b.size == 50
        assert samples_b.user == b
        assert next(samples_b).user == b
        assert next(samples_b).name.startswith('Sample B ')

        samples_admin = self.session.samples(user=admin)
        assert samples_admin.size == 0
        assert samples_admin.user == admin
        with pytest.raises(StopIteration):
            next(samples_admin)
