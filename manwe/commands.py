# -*- coding: utf-8 -*-
"""
Manwë command line interface.

Todo: Move some of the docstring from the _old_population_study.py file here.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import argparse
import getpass
import os
import re
import sys

from .config import Config
from .errors import (ApiError, BadRequestError, UnauthorizedError,
                     ForbiddenError, NotFoundError)
from .resources import USER_ROLES
from .session import Session


SYSTEM_CONFIGURATION = '/etc/manwe/config'
USER_CONFIGURATION = os.path.join(
    os.environ.get('XDG_CONFIG_HOME', None) or
    os.path.join(os.path.expanduser('~'), '.config'),
    'manwe', 'config')


class UserError(Exception):
    pass


def log(message):
    sys.stderr.write('%s\n' % message)


def abort(message=None):
    if message:
        log('error: %s' % message)
    sys.exit(1)


def list_samples(session, public=False, user=None, groups=None):
    """
    List samples.
    """
    groups = groups or []

    filters = {}
    if public:
        filters.update(public=True)
    if user:
        filters.update(user=user)
    if groups:
        filters.update(groups=groups)

    samples = session.samples(**filters)

    for i, sample in enumerate(samples):
        if i:
            print
        print 'Sample:      %s' % sample.uri
        print 'Name:        %s' % sample.name
        print 'Pool size:   %i' % sample.pool_size
        print 'Visibility:  %s' % ('public' if sample.public else 'private')
        print 'State:       %s' % ('active' if sample.active else 'inactive')


def show_sample(session, uri):
    """
    Show sample details.
    """
    try:
        sample = session.sample(uri)
    except NotFoundError:
        raise UserError('Sample does not exist: "%s"' % uri)

    print 'Sample:      %s' % sample.uri
    print 'Name:        %s' % sample.name
    print 'Pool size:   %i' % sample.pool_size
    print 'Visibility:  %s' % ('public' if sample.public else 'private')
    print 'State:       %s' % ('active' if sample.active else 'inactive')

    print
    print 'User:        %s' % sample.user.uri
    print 'Name:        %s' % sample.user.name

    for group in sample.groups:
        print
        print 'Group:       %s' % group.uri
        print 'Name:        %s' % group.name

    for variation in session.variations(sample=sample):
        print
        print 'Variation:   %s' % variation.uri
        print 'State:       %s' % ('imported' if variation.task['done'] else 'not imported')

    for coverage in session.coverages(sample=sample):
        print
        print 'Coverage:    %s' % coverage.uri
        print 'State:       %s' % ('imported' if coverage.task['done'] else 'not imported')


def activate_sample(session, uri):
    """
    Activate sample.
    """
    try:
        sample = session.sample(uri)
    except NotFoundError:
        raise UserError('Sample does not exist: "%s"' % uri)

    sample.active = True
    sample.save()

    log('Activated sample: %s' % sample.uri)


def annotate_sample_variations(session, uri, queries=None):
    """
    Annotate sample variations with variant frequencies.
    """
    queries = queries or {}

    try:
        sample = session.sample(uri)
    except NotFoundError:
        raise UserError('Sample does not exist: "%s"' % uri)

    for variation in session.variations(sample=sample):
        annotation = session.create_annotation(
            variation.data_source, queries=queries)
        log('Started annotation: %s' % annotation.uri)


def add_sample(session, name, groups=None, pool_size=1, public=False,
               no_coverage_profile=False):
    """
    Add sample.
    """
    groups = groups or []

    if pool_size < 1:
        raise UserError('Pool size should be at least 1')

    groups = [session.group(uri) for uri in groups]
    sample = session.create_sample(name, groups=groups, pool_size=pool_size,
                                   coverage_profile=not no_coverage_profile,
                                   public=public)

    log('Added sample: %s' % sample.uri)
    return sample


def import_sample(session, name, groups=None, pool_size=1, public=False,
                  no_coverage_profile=False, vcf_files=None, bed_files=None,
                  data_uploaded=False, prefer_genotype_likelihoods=False):
    """
    Add sample and import variation and coverage files.
    """
    vcf_files = vcf_files or []
    bed_files = bed_files or []

    if not no_coverage_profile and not bed_files:
        raise UserError('Expected at least one BED file')

    # Todo: Nice error if file cannot be read.
    vcf_sources = [({'local_file': vcf_file}, vcf_file) if data_uploaded else
                   ({'data': open(vcf_file)}, vcf_file)
                   for vcf_file in vcf_files]
    bed_sources = [({'local_file': bed_file}, bed_file) if data_uploaded else
                   ({'data': open(bed_file)}, bed_file)
                   for bed_file in bed_files]

    sample = add_sample(session, name, groups=groups, pool_size=pool_size,
                        public=public, no_coverage_profile=no_coverage_profile)

    for source, filename in vcf_sources:
        data_source = session.create_data_source(
            'Variants from file "%s"' % filename,
            filetype='vcf',
            gzipped=filename.endswith('.gz'),
            **source)
        log('Added data source: %s' % data_source.uri)
        variation = session.create_variation(
            sample, data_source,
            prefer_genotype_likelihoods=prefer_genotype_likelihoods)
        log('Started variation import: %s' % variation.uri)

    for source, filename in bed_sources:
        data_source = session.create_data_source(
            'Regions from file "%s"' % filename,
            filetype='bed',
            gzipped=filename.endswith('.gz'),
            **source)
        log('Added data source: %s' % data_source.uri)
        coverage = session.create_coverage(sample, data_source)
        log('Started coverage import: %s' % coverage.uri)


def import_variation(session, uri, vcf_file, data_uploaded=False,
                     prefer_genotype_likelihoods=False):
    """
    Import variation file for existing sample.
    """
    # Todo: Nice error if file cannot be read.
    if data_uploaded:
        source = {'local_file': vcf_file}
    else:
        source = {'data': open(vcf_file)}

    try:
        sample = session.sample(uri)
    except NotFoundError:
        raise UserError('Sample does not exist: "%s"' % uri)

    data_source = session.create_data_source(
        'Variants from file "%s"' % vcf_file,
        filetype='vcf',
        gzipped=vcf_file.endswith('.gz'),
        **source)
    log('Added data source: %s' % data_source.uri)
    variation = session.create_variation(
        sample, data_source,
        prefer_genotype_likelihoods=prefer_genotype_likelihoods)
    log('Started variation import: %s' % variation.uri)


def import_coverage(session, uri, bed_file, data_uploaded=False):
    """
    Import coverage file for existing sample.
    """
    # Todo: Nice error if file cannot be read.
    if data_uploaded:
        source = {'local_file': bed_file}
    else:
        source = {'data': open(bed_file)}

    try:
        sample = session.sample(uri)
    except NotFoundError:
        raise UserError('Sample does not exist: "%s"' % uri)

    data_source = session.create_data_source(
        'Regions from file "%s"' % bed_file,
        filetype='bed',
        gzipped=bed_file.endswith('.gz'),
        **source)
    log('Added data source: %s' % data_source.uri)
    coverage = session.create_coverage(sample, data_source)
    log('Started coverage import: %s' % coverage.uri)


def list_groups(session):
    """
    List groups.
    """
    groups = session.groups()

    for i, group in enumerate(groups):
        if i:
            print
        print 'Group:  %s' % group.uri
        print 'Name:   %s' % group.name


def show_group(session, uri):
    """
    Show group details.
    """
    try:
        group = session.group(uri)
    except NotFoundError:
        raise UserError('Group does not exist: "%s"' % uri)

    print 'Group:  %s' % group.uri
    print 'Name:   %s' % group.name


def add_group(session, name):
    """
    Add a sample group.
    """
    group = session.create_group(name)

    log('Added group: %s' % group.uri)


def list_users(session):
    """
    List users.
    """
    users = session.users()

    for i, user in enumerate(users):
        if i:
            print
        print 'User:   %s' % user.uri
        print 'Name:   %s' % user.name
        print 'Login:  %s' % user.login
        print 'Roles:  %s' % ', '.join(sorted(user.roles))


def show_user(session, uri):
    """
    Show user details.
    """
    try:
        user = session.user(uri)
    except NotFoundError:
        raise UserError('User does not exist: "%s"' % uri)

    print 'User:   %s' % user.uri
    print 'Name:   %s' % user.name
    print 'Login:  %s' % user.login
    print 'Roles:  %s' % ', '.join(sorted(user.roles))


def add_user(session, login, name=None, roles=None):
    """
    Add an API user (queries for password).
    """
    roles = roles or []
    name = name or login

    if not re.match('[a-zA-Z][a-zA-Z0-9._-]*$', login):
        raise UserError('User login must match "[a-zA-Z][a-zA-Z0-9._-]*"')

    password = getpass.getpass('Please provide a password for the new user: ')
    password_control = getpass.getpass('Repeat: ')
    if password != password_control:
        raise UserError('Passwords did not match')

    user = session.create_user(login, password, name=name, roles=roles)

    log('Added user: %s' % user.uri)


def list_data_sources(session, user=None):
    """
    List data sources.
    """
    filters = {}
    if user:
        filters.update(user=user)

    data_sources = session.data_sources(**filters)

    for i, data_source in enumerate(data_sources):
        if i:
            print
        print 'Data source:  %s' % data_source.uri
        print 'Name:         %s' % data_source.name
        print 'Filetype:     %s' % data_source.filetype


def show_data_source(session, uri):
    """
    Show data source details.
    """
    try:
        data_source = session.data_source(uri)
    except NotFoundError:
        raise UserError('Data source does not exist: "%s"' % uri)

    print 'Data source:  %s' % data_source.uri
    print 'Name:         %s' % data_source.name
    print 'Filetype:     %s' % data_source.filetype

    print
    print 'User:         %s' % data_source.user.uri
    print 'Name:         %s' % data_source.user.name


def data_source_data(session, uri):
    """
    Download data source and write data to standard output.
    """
    try:
        data_source = session.data_source(uri)
    except NotFoundError:
        raise UserError('Data source does not exist: "%s"' % uri)

    for chunk in data_source.data:
        sys.stdout.write(chunk)


def annotate_data_source(session, uri, queries=None):
    """
    Annotate data source with variant frequencies.
    """
    queries = queries or {}

    try:
        data_source = session.data_source(uri)
    except NotFoundError:
        raise UserError('Data source does not exist: "%s"' % uri)

    annotation = session.create_annotation(
        data_source, queries=queries)
    log('Started annotation: %s' % annotation.uri)


def annotate_vcf(session, vcf_file, data_uploaded=False, queries=None):
    """
    Annotate VCF file with variant frequencies.
    """
    queries = queries or {}

    # Todo: Nice error if file cannot be read.
    if data_uploaded:
        source = {'local_file': vcf_file}
    else:
        source = {'data': open(vcf_file)}

    data_source = session.create_data_source(
        'Variants from file "%s"' % vcf_file,
        filetype='vcf',
        gzipped=vcf_file.endswith('.gz'),
        **source)
    log('Added data source: %s' % data_source.uri)
    annotation = session.create_annotation(
        data_source, queries=queries)
    log('Started annotation: %s' % annotation.uri)


def annotate_bed(session, bed_file, data_uploaded=False, queries=None):
    """
    Annotate BED file with variant frequencies.
    """
    queries = queries or {}

    # Todo: Nice error if file cannot be read.
    if data_uploaded:
        source = {'local_file': bed_file}
    else:
        source = {'data': open(bed_file)}

    data_source = session.create_data_source(
        'Regions from file "%s"' % bed_file,
        filetype='bed',
        gzipped=bed_file.endswith('.gz'),
        **source)
    log('Added data source: %s' % data_source.uri)
    annotation = session.create_annotation(
        data_source, queries=queries)
    log('Started annotation: %s' % annotation.uri)


def create_config(filename=None):
    """
    Create a Manwë configuration object.

    Configuration values are initialized from the :mod:`manwe.default_config`
    module.

    By default, configuration values are then read from two locations, in this
    order:

    1. `SYSTEM_CONFIGURATION`
    2. `USER_CONFIGURATION`

    If both files exist, values defined in the second overwrite values defined
    in the first.

    An exception to this is when the optional `filename` argument is set. In
    that case, the locations listed above are ignored and the configuration is
    read from `filename`.

    :arg filename: Optional filename to read configuration from. If present,
      this overrides automatic detection of configuration file location.
    :type filename: str

    :return: Manwë configuration object.
    :rtype: config.Config
    """
    config = Config()

    if filename:
        config.from_pyfile(filename)
    else:
        if os.path.isfile(SYSTEM_CONFIGURATION):
            config.from_pyfile(SYSTEM_CONFIGURATION)
        if os.path.isfile(USER_CONFIGURATION):
            config.from_pyfile(USER_CONFIGURATION)

    return config


def main():
    """
    Manwë command line interface.
    """
    class UpdateAction(argparse.Action):
        """
        Custom argparse action to store a pair of values as key and value in a
        dictionary.

        Example usage::

            >>> p.add_argument(
            ...     '-c', dest='flower_colors', nargs=2,
            ...     metavar=('FLOWER', 'COLOR'), action=UpdateAction,
            ...     help='set flower color (multiple allowed)')
        """
        def __init__(self, *args, **kwargs):
            if kwargs.get('nargs') != 2:
                raise ValueError('nargs for update actions must be 2')
            super(UpdateAction, self).__init__(*args, **kwargs)
        def  __call__(self, parser, namespace, values, option_string=None):
            key, value = values
            d = getattr(namespace, self.dest) or {}
            d[key] = value
            setattr(namespace, self.dest, d)

    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        '-c', '--config', metavar='FILE', type=str, dest='config',
        help='path to configuration file to use instead of looking in '
        'default locations')

    parser = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0], parents=[config_parser])
    subparsers = parser.add_subparsers(
        title='subcommands', dest='subcommand', help='subcommand help')

    # Subparsers for 'samples'.
    s = subparsers.add_parser(
        'samples', help='manage samples', description='Manage sample resources.'
    ).add_subparsers()

    # Subparser 'samples list'.
    p = s.add_parser(
        'list', help='list samples',
        description=list_samples.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=list_samples)
    p.add_argument(
        '-p', '--public', dest='public', action='store_true',
        help='only public samples')
    p.add_argument(
        '-u', '--user', dest='user', metavar='URI',
        help='filter samples by user')
    p.add_argument(
        '-g', '--group', dest='groups', metavar='URI', action='append',
        help='filter samples by group (more than one allowed)')

    # Subparser 'samples show'.
    p = s.add_parser(
        'show', help='show sample details',
        description=show_sample.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=show_sample)
    p.add_argument(
        'uri', metavar='URI', type=str, help='sample')

    # Subparser 'samples activate'.
    p = s.add_parser(
        'activate', help='activate sample',
        description=activate_sample.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=activate_sample)
    p.add_argument(
        'uri', metavar='URI', type=str, help='sample')

    # Subparser 'samples annotate-variations'.
    p = s.add_parser(
        'annotate-variations', help='annotate sample variations',
        description=annotate_sample_variations.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=annotate_sample_variations)
    p.add_argument(
        'uri', metavar='URI', type=str, help='sample')
    p.add_argument(
        '-q', '--query', dest='queries', nargs=2, action=UpdateAction,
        metavar=('NAME', 'EXPRESSION'), help='annotation query (more than '
        'one allowed)')

    # Subparser 'samples add'.
    p = s.add_parser(
        'add', help='add sample',
        description=add_sample.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=add_sample)
    p.add_argument(
        'name', metavar='NAME', type=str, help='sample name')
    p.add_argument(
        '-g', '--group', dest='groups', metavar='URI', action='append',
        help='sample group (more than one allowed)')
    p.add_argument(
        '-s', '--pool-size', dest='pool_size', default=1, type=int,
        help='number of individuals in sample (default: 1)')
    p.add_argument(
        '-p', '--public', dest='public', action='store_true',
        help='sample data is public')
    p.add_argument(
        '--no-coverage-profile', dest='no_coverage_profile', action='store_true',
        help='sample has no coverage profile')

    # Subparser 'samples import'.
    p = s.add_parser(
        'import', help='add sample and import data',
        description=import_sample.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=import_sample)
    p.add_argument(
        'name', metavar='NAME', type=str, help='sample name')
    p.add_argument(
        '-g', '--group', dest='groups', metavar='URI', action='append',
        help='sample group (more than one allowed)')
    p.add_argument(
        '--vcf', metavar='VCF_FILE', dest='vcf_files', action='append',
        required=True, help='file in VCF 4.1 format to import variants from '
        '(more than one allowed)')
    p.add_argument(
        '--bed', metavar='BED_FILE', dest='bed_files', action='append',
        help='file in BED format to import covered regions from (more than '
        'one allowed)')
    p.add_argument(
        '-u', '--data-uploaded', dest='data_uploaded', action='store_true',
        help='data files are already uploaded to the server')
    p.add_argument(
        '-s', '--pool-size', dest='pool_size', default=1, type=int,
        help='number of individuals in sample (default: 1)')
    p.add_argument(
        '-p', '--public', dest='public', action='store_true',
        help='sample data is public')
    # Note: We prefer to explicitely include the --no-coverage-profile instead
    #     of concluding it from an empty list of BED files. This prevents
    #     accidentally forgetting the coverage profile.
    p.add_argument(
        '--no-coverage-profile', dest='no_coverage_profile', action='store_true',
        help='sample has no coverage profile')
    p.add_argument(
        '-l', '--prefer_genotype_likelihoods', dest='prefer_genotype_likelihoods',
        action='store_true', help='in VCF files, derive genotypes from '
        'likelihood scores instead of using reported genotypes (use this if '
        'the file was produced by samtools)')

    # Subparser 'samples import-vcf'.
    p = s.add_parser(
        'import-vcf', help='import VCF file for existing sample',
        description=import_variation.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=import_variation)
    p.add_argument(
        'uri', metavar='URI', type=str, help='sample')
    p.add_argument(
        'vcf_file', metavar='FILE',
        help='file in VCF 4.1 format to import variants from')
    p.add_argument(
        '-u', '--data-uploaded', dest='data_uploaded', action='store_true',
        help='data files are already uploaded to the server')
    p.add_argument(
        '-l', '--prefer_genotype_likelihoods', dest='prefer_genotype_likelihoods',
        action='store_true', help='in VCF files, derive genotypes from '
        'likelihood scores instead of using reported genotypes (use this if '
        'the file was produced by samtools)')

    # Subparser 'samples import-bed'.
    p = s.add_parser(
        'import-bed', help='import BED file for existing sample',
        description=import_coverage.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=import_coverage)
    p.add_argument(
        'uri', metavar='URI', type=str, help='sample')
    p.add_argument(
        'bed_file', metavar='FILE',
        help='file in BED format to import covered regions from')
    p.add_argument(
        '-u', '--data-uploaded', dest='data_uploaded', action='store_true',
        help='data files are already uploaded to the server')

    # Subparsers for 'groups'.
    s = subparsers.add_parser(
        'groups', help='manage groups', description='Manage group resources.'
    ).add_subparsers()

    # Subparser 'groups list'.
    p = s.add_parser(
        'list', help='list groups',
        description=list_groups.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=list_groups)

    # Subparser 'groups show'.
    p = s.add_parser(
        'show', help='show group details',
        description=show_group.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=show_group)
    p.add_argument(
        'uri', metavar='URI', type=str, help='group')

    # Subparser 'groups add'.
    p = s.add_parser(
        'add', help='add new sample group',
        description=add_group.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=add_group)
    p.add_argument(
        'name', metavar='NAME', type=str, help='group name')

    # Subparsers for 'users'.
    s = subparsers.add_parser(
        'users', help='manage users', description='Manage user resources.'
    ).add_subparsers()

    # Subparser 'users list'.
    p = s.add_parser(
        'list', help='list users',
        description=list_users.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=list_users)

    # Subparser 'users show'.
    p = s.add_parser(
        'show', help='show user details',
        description=show_user.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=show_user)
    p.add_argument('uri', metavar='URI', type=str, help='user')

    # Subparser 'users add'.
    p = s.add_parser(
        'add', help='add new API user',
        description=add_user.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=add_user)
    p.add_argument(
        'login', metavar='LOGIN', type=str, help='user login')
    p.add_argument(
        '-n', '--name', metavar='NAME', dest='name', type=str,
        help='user name (default: LOGIN)')
    for role in USER_ROLES:
        p.add_argument(
            '--%s' % role, dest='roles', action='append_const', const=role,
            help='user has %s role' % role)

    # Subparsers for 'data-sources'.
    s = subparsers.add_parser(
        'data-sources', help='manage data sources',
        description='Manage data source resources.'
    ).add_subparsers()

    # Subparser 'data-sources list'.
    p = s.add_parser(
        'list', help='list data sources',
        description=list_data_sources.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=list_data_sources)
    p.add_argument(
        '-u', '--user', dest='user', metavar='URI',
        help='filter data sources by user')

    # Subparser 'data-sources show'.
    p = s.add_parser(
        'show', help='show data source details',
        description=show_data_source.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=show_data_source)
    p.add_argument(
        'uri', metavar='URI', type=str, help='data source')

    # Subparser 'data-sources download'.
    p = s.add_parser(
        'download', help='download data source',
        description=data_source_data.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=data_source_data)
    p.add_argument(
        'uri', metavar='URI', type=str, help='data source')

    # Subparser 'data-sources annotate'.
    p = s.add_parser(
        'annotate', help='annotate data source',
        description=annotate_data_source.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=annotate_data_source)
    p.add_argument(
        'uri', metavar='URI', type=str, help='data source')
    p.add_argument(
        '-q', '--query', dest='queries', nargs=2, action=UpdateAction,
        metavar=('NAME', 'EXPRESSION'), help='annotation query (more than '
        'one allowed)')

    # Subparser 'annotate-vcf'.
    p = subparsers.add_parser(
        'annotate-vcf', help='annotate VCF file',
        description=annotate_vcf.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=annotate_vcf)
    p.add_argument(
        'vcf_file', metavar='FILE', help='file in VCF 4.1 format to annotate')
    p.add_argument(
        '-u', '--data-uploaded', dest='data_uploaded', action='store_true',
        help='data files are already uploaded to the server')
    p.add_argument(
        '-q', '--query', dest='queries', nargs=2, action=UpdateAction,
        metavar=('NAME', 'EXPRESSION'), help='annotation query (more than '
        'one allowed)')

    # Subparser 'annotate-bed'.
    p = subparsers.add_parser(
        'annotate-bed', help='annotate BED file',
        description=annotate_bed.__doc__.split('\n\n')[0],
        parents=[config_parser])
    p.set_defaults(func=annotate_bed)
    p.add_argument(
        'bed_file', metavar='FILE', help='file in BED format to annotate')
    p.add_argument(
        '-u', '--data-uploaded', dest='data_uploaded', action='store_true',
        help='data files are already uploaded to the server')
    p.add_argument(
        '-q', '--query', dest='queries', nargs=2, action=UpdateAction,
        metavar=('NAME', 'EXPRESSION'), help='annotation query (more than '
        'one allowed)')

    args = parser.parse_args()

    try:
        session = Session(config=create_config(args.config))
        args.func(session=session,
                  **{k: v for k, v in vars(args).items()
                     if k not in ('config', 'func', 'subcommand')})
    except UserError as e:
        abort(e)
    except UnauthorizedError:
        abort('Authentication is needed, please make sure you have the '
              'correct authentication token defined in "%s"'
              % (args.config or USER_CONFIGURATION))
    except ForbiddenError:
        abort('Sorry, you do not have permission')
    except BadRequestError as (code, message):
        abort(message)
    except ApiError as (code, message):
        abort(message)


if __name__ == '__main__':
    main()
