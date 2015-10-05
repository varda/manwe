"""
Unit tests for :mod:`manwe.session`.
"""


import os
import gzip
import zlib

import pytest
import varda
import varda.models
import varda.tasks

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

    def test_create_annotation(self):
        """
        Create an annotation.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.DataSource(
            admin, 'test data source', 'vcf', local_file='test.vcf.gz',
            gzipped=True))
        varda.db.session.commit()

        data_source_uri = self.uri_for_data_source(name='test data source')
        data_source = self.session.data_source(data_source_uri)

        annotation = self.session.create_annotation(data_source, name='test annotation')

        annotation_uri = self.uri_for_annotation()
        assert annotation.uri == annotation_uri

    def test_create_annotation_name(self):
        """
        Create an annotation and check for name.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.DataSource(
            admin, 'test data source', 'vcf', local_file='test.vcf.gz',
            gzipped=True))
        varda.db.session.commit()

        data_source_uri = self.uri_for_data_source(name='test data source')
        data_source = self.session.data_source(data_source_uri)

        self.session.create_annotation(data_source, name='test annotation')
        varda.models.DataSource.query.filter_by(name='test annotation').one()

    def test_annotation_task(self):
        """
        Create an annotation and check task state.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.DataSource(
            admin, 'test data source', 'vcf', local_file='test.vcf.gz',
            gzipped=True))
        varda.db.session.commit()

        data_source_uri = self.uri_for_data_source(name='test data source')
        data_source = self.session.data_source(data_source_uri)

        annotation = self.session.create_annotation(data_source)
        task = annotation.task

        assert task.waiting
        assert not task.running
        assert not task.success
        assert not task.failure
        assert task.error is None

        # Mannually run task.
        varda_annotation = varda.models.Annotation.query.one()
        result = varda.tasks.write_annotation.apply(args=[varda_annotation.id])
        varda_annotation.task_uuid = result.task_id
        varda.db.session.commit()

        annotation.refresh()

        assert not task.waiting
        assert not task.running
        assert task.success
        assert not task.failure
        assert task.error is None

    def test_annotation_task_wait(self):
        """
        Create an annotation and wait for task.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.DataSource(
            admin, 'test data source', 'vcf', local_file='test.vcf.gz',
            gzipped=True))
        varda.db.session.commit()

        data_source_uri = self.uri_for_data_source(name='test data source')
        data_source = self.session.data_source(data_source_uri)

        annotation = self.session.create_annotation(data_source)
        task = annotation.task

        percentages = task.wait_and_monitor()
        assert next(percentages) is None
        assert next(percentages) is None

        assert task.waiting
        assert not task.running
        assert not task.success
        assert not task.failure
        assert task.error is None

        # Mannually run task.
        varda_annotation = varda.models.Annotation.query.one()
        result = varda.tasks.write_annotation.apply(args=[varda_annotation.id])
        varda_annotation.task_uuid = result.task_id
        varda.db.session.commit()

        assert next(percentages) == 100
        with pytest.raises(StopIteration):
            next(percentages)

        assert not task.waiting
        assert not task.running
        assert task.success
        assert not task.failure
        assert task.error is None

    def test_create_annotation_task_resubmit(self):
        """
        Create an annotation and resubmit task.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.DataSource(
            admin, 'test data source', 'vcf', local_file='test.vcf.gz',
            gzipped=True))
        varda.db.session.commit()

        data_source_uri = self.uri_for_data_source(name='test data source')
        data_source = self.session.data_source(data_source_uri)

        annotation = self.session.create_annotation(data_source)
        task = annotation.task

        assert task.waiting
        assert not task.running
        assert not task.success
        assert not task.failure
        assert task.error is None

        # Mannually run task.
        varda_annotation = varda.models.Annotation.query.one()
        result = varda.tasks.write_annotation.apply(args=[varda_annotation.id])
        varda_annotation.task_uuid = result.task_id
        varda.db.session.commit()

        annotation.refresh()

        assert not task.waiting
        assert not task.running
        assert task.success
        assert not task.failure
        assert task.error is None

        task.resubmit()

        assert task.waiting
        assert not task.running
        assert not task.success
        assert not task.failure
        assert task.error is None

        # Mannually run task.
        varda_annotation = varda.models.Annotation.query.one()
        result = varda.tasks.write_annotation.apply(args=[varda_annotation.id])
        varda_annotation.task_uuid = result.task_id
        varda.db.session.commit()

        annotation.refresh()

        assert not task.waiting
        assert not task.running
        assert task.success
        assert not task.failure
        assert task.error is None

    def test_samples_by_public(self):
        """
        Filter sample collection by public status.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Private sample', public=False))
        varda.db.session.add(varda.models.Sample(admin, 'Public sample', public=True))
        varda.db.session.commit()

        # All samples.
        samples = self.session.samples()
        assert samples.size == 2
        assert samples.public is None

        # Private samples.
        samples = self.session.samples(public=False)
        assert samples.size == 1
        assert not samples.public
        sample = next(samples)
        assert not sample.public
        assert sample.name == 'Private sample'

        # Public samples.
        samples = self.session.samples(public=True)
        assert samples.size == 1
        assert samples.public
        sample = next(samples)
        assert sample.public
        assert sample.name == 'Public sample'

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

    def test_samples_by_groups(self):
        """
        Filter sample collection by groups.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        a = varda.models.Group('Group A')
        b = varda.models.Group('Group B')

        varda.db.session.add(a)
        varda.db.session.add(b)
        varda.db.session.add_all(
            varda.models.Sample(admin, 'Sample A %d' % i, groups=[a])
            for i in range(20))
        varda.db.session.add_all(
            varda.models.Sample(admin, 'Sample B %d' % i, groups=[b])
            for i in range(20))
        varda.db.session.add_all(
            varda.models.Sample(admin, 'Sample AB %d' % i, groups=[a, b])
            for i in range(20))
        varda.db.session.commit()

        a = self.session.group(self.uri_for_group(name='Group A'))
        b = self.session.group(self.uri_for_group(name='Group B'))

        # All samples.
        samples = self.session.samples()
        assert samples.size == 60

        # Group A samples.
        samples_a = self.session.samples(groups=[a])
        assert samples_a.size == 40
        assert samples_a.groups == {a}
        sample = next(samples_a)
        assert any(g == a for g in sample.groups)
        assert sample.name.startswith('Sample A ') or sample.name.startswith('Sample AB ')

        # Group B samples.
        samples_b = self.session.samples(groups={b})
        assert samples_b.size == 40
        assert samples_b.groups == {b}
        sample = next(samples_b)
        assert any(g == b for g in sample.groups)
        assert sample.name.startswith('Sample B ') or sample.name.startswith('Sample AB ')

        # Group A and B samples.
        samples_ab = self.session.samples(groups=[a, b])
        assert samples_ab.size == 20
        assert samples_ab.groups == {a, b}
        sample = next(samples_ab)
        assert any(g == a for g in sample.groups)
        assert any(g == b for g in sample.groups)
        assert sample.name.startswith('Sample AB ')

    def test_variant_annotate(self):
        """
        Annotate a variant.
        """
        variant = self.session.create_variant('chr8', 800000, 'T', 'A')
        annotations = variant.annotate(queries={'GLOBAL': '*'})

        assert annotations == {'GLOBAL': {'coverage': 0,
                                          'frequency': 0,
                                          'frequency_het': 0,
                                          'frequency_hom': 0}}

    def test_variant_normalize(self):
        """
        Normalize a variant.
        """
        variant = self.session.create_variant('chr8', 800000, 'ATTTT', 'ATTTTT')

        assert variant.chromosome == '8'
        assert variant.position == 800001
        assert variant.reference == ''
        assert variant.observed == 'T'

    def test_upload_data_source(self):
        """
        Upload a data source.
        """
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'test.vcf')

        with open(filename) as vcf_file:
            data_source = self.session.create_data_source('Test VCF', 'vcf',
                                                          data=vcf_file)

        with open(filename) as vcf_file:
            assert zlib.decompress(''.join(data_source.data),
                                   16 + zlib.MAX_WBITS) == vcf_file.read()

    def test_upload_data_source_gzipped(self):
        """
        Upload a gzipped data source.
        """
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'test.vcf.gz')

        with open(filename, 'rb') as vcf_file:
            data_source = self.session.create_data_source('Test VCF', 'vcf',
                                                          gzipped=True,
                                                          data=vcf_file)

        with gzip.open(filename) as vcf_file:
            assert zlib.decompress(''.join(data_source.data),
                                   16 + zlib.MAX_WBITS) == vcf_file.read()

    def test_modify_sample(self):
        """
        Modify a sample.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        assert not sample.dirty
        sample.name = 'Modified Sample'
        assert sample.dirty

    def test_save_sample(self):
        """
        Save a sample.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        assert not sample.dirty
        sample.name = 'Modified Sample'
        assert sample.dirty
        sample.save()
        assert not sample.dirty

        assert varda.models.Sample.query.filter_by(
            name='Modified Sample').count() == 1

    def test_save_modified_sample(self):
        """
        Save a modified sample.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        assert not sample.dirty
        sample.pool_size = 42
        assert sample.dirty

        varda.models.Sample.query.filter_by(
            name='Sample').one().name = 'Modified Sample'
        varda.db.session.commit()

        assert sample.pool_size == 42
        assert sample.name == 'Sample'
        sample.save()
        assert sample.name == 'Modified Sample'
        assert sample.pool_size == 42
        assert not sample.dirty

        assert varda.models.Sample.query.filter_by(
            name='Modified Sample', pool_size=42).count() == 1

    def test_save_fields_sample(self):
        """
        Save a sample field.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        assert sample.name == 'Sample'
        assert not sample.dirty
        sample.save_fields(name='Modified Sample')
        assert not sample.dirty
        assert sample.name == 'Modified Sample'

        assert varda.models.Sample.query.filter_by(
            name='Modified Sample').count() == 1

    def test_save_fields_modified_sample(self):
        """
        Save a modified sample field.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        varda.models.Sample.query.filter_by(
            name='Sample').one().name = 'Modified Sample'
        varda.db.session.commit()

        assert sample.name == 'Sample'
        assert sample.pool_size == 1
        assert not sample.dirty
        sample.save_fields(pool_size=42)
        assert not sample.dirty
        assert sample.name == 'Modified Sample'
        assert sample.pool_size == 42

        assert varda.models.Sample.query.filter_by(
            name='Modified Sample', pool_size=42).count() == 1

    def test_save_fields_modified_both_sample(self):
        """
        Save a modified sample (local and on server) field.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        varda.models.Sample.query.filter_by(
            name='Sample').one().name = 'Modified Sample'
        varda.db.session.commit()

        assert sample.name == 'Sample'
        assert sample.pool_size == 1
        assert not sample.public
        assert not sample.dirty

        sample.public = True
        assert sample.dirty
        sample.save_fields(pool_size=42)
        assert sample.dirty
        assert sample.name == 'Modified Sample'
        assert sample.pool_size == 42
        assert sample.public

        assert varda.models.Sample.query.filter_by(
            name='Modified Sample', pool_size=42, public=False).count() == 1

    def test_refresh_sample(self):
        """
        Refresh a sample.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        varda.models.Sample.query.filter_by(
            name='Sample').one().name = 'Modified Sample'
        varda.db.session.commit()

        assert sample.name == 'Sample'
        sample.refresh()
        assert sample.name == 'Modified Sample'

    def test_refresh_modified_sample(self):
        """
        Refresh a modified sample.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        assert not sample.dirty
        sample.pool_size = 42
        assert sample.dirty

        varda.models.Sample.query.filter_by(
            name='Sample').one().name = 'Modified Sample'
        varda.db.session.commit()

        assert sample.pool_size == 42
        assert sample.name == 'Sample'
        sample.refresh()
        assert sample.name == 'Modified Sample'
        assert sample.pool_size == 1
        assert not sample.dirty

    def test_refresh_modified_sample_skip_dirty(self):
        """
        Refresh a modified sample skipping dirty fields.
        """
        admin = varda.models.User.query.filter_by(name='Administrator').one()
        varda.db.session.add(varda.models.Sample(admin, 'Sample'))
        varda.db.session.commit()

        sample_uri = self.uri_for_sample(name='Sample')
        sample = self.session.sample(sample_uri)

        assert not sample.dirty
        sample.pool_size = 42
        assert sample.dirty

        varda.models.Sample.query.filter_by(
            name='Sample').one().name = 'Modified Sample'
        varda.db.session.commit()

        assert sample.pool_size == 42
        assert sample.name == 'Sample'
        sample.refresh(skip_dirty=True)
        assert sample.name == 'Modified Sample'
        assert sample.pool_size == 42
        assert sample.dirty
