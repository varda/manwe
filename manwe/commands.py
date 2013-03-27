# -*- coding: utf-8 -*-
"""
Manwë command line interface.

Todo: Move some of the docstring from the _old_population_study.py file here.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import argparse
import re
import sys

from . import config
from .errors import (ApiError, BadRequestError, UnauthorizedError,
                     ForbiddenError, NotFoundError)
from .session import Session


def log(message):
    sys.stderr.write(message + '\n')


def abort(message=None):
    if message:
        log(message)
    sys.exit(1)


def import_sample(name, pool_size=1, public=False, no_coverage_profile=False,
                  vcf_files=None, bed_files=None, data_uploaded=False,
                  config=None):
    """
    Add sample and import variantion and coverage files.
    """
    vcf_files = vcf_files or []
    bed_files = bed_files or []

    if pool_size < 1:
        abort('Pool size should be at least 1')

    if not no_coverage_profile and not bed_files:
        abort('Expected at least one BED file')

    # Todo: Nice error if file cannot be read.
    vcf_sources = [({'local_file': vcf_file}, vcf_file) if data_uploaded else
                   ({'data': open(vcf_file)}, vcf_file.name)
                   for vcf_file in vcf_files]
    bed_sources = [({'local_file': bed_file}, bed_file) if data_uploaded else
                   ({'data': open(bed_file)}, bed_file.name)
                   for bed_file in bed_files]

    session = Session(config=config)

    sample = session.add_sample(name, pool_size=pool_size,
                                coverage_profile=not coverage_profile,
                                public=public)

    for source, filename in vcf_sources:
        data_source = session.add_data_source(
            'Variants from file "%s"' % filename,
            filetype='vcf',
            gzipped=filename.endswith('.gz'),
            **source)
        session.add_variation(sample, data_source)

    for source, filename in bed_sources:
        data_source = session.add_data_source(
            'Regions from file "%s"' % filename,
            filetype='bed',
            gzipped=filename.endswith('.gz'),
            **source)
        session.add_coverage(sample, data_source)


def show_sample(uri, config=None):
    """
    Show sample details.
    """
    session = Session(config=config)
    sample = session.sample(uri)

    print 'Sample:  %s' % sample.uri
    print 'Name:    %s' % sample.name


def add_user(login, password, name=None, config=None, **kwargs):
    """
    Add an API user.
    """
    name = name or login

    if not re.match('[a-zA-Z][a-zA-Z0-9._-]*$', login):
        abort('User login must match "[a-zA-Z][a-zA-Z0-9._-]*"')

    session = Session(config=config)

    # Todo: Define roles as constant.
    roles = ('admin', 'importer', 'annotator', 'trader')
    selected_roles = [role for role in roles if kwargs.get(role)]

    user = session.add_user(login, password, name=name, roles=selected_roles)

    log('Added user: %s' % user.uri)


def show_user(uri, config=None):
    """
    Show user details.
    """
    session = Session(config=config)

    try:
        user = session.user(uri)
    except NotFoundError:
        abort('User does not exist: "%s"' % uri)

    print 'User:   %s' % user.uri
    print 'Name:   %s' % user.name
    print 'Login:  %s' % user.login
    print 'Roles:  %s' % ', '.join(sorted(user.roles))


def main():
    """
    Manwë command line interface.
    """
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument('--config', metavar='CONFIG_FILE', type=str,
                               dest='config', help='path to configuration file '
                               'to use instead of looking in default locations')

    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                     parents=[config_parser])

    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    p = subparsers.add_parser('import-sample', help='import sample data',
                              description=import_sample.__doc__.split('\n\n')[0],
                              parents=[config_parser])
    p.set_defaults(func=import_sample)
    p.add_argument('name', metavar='NAME', type=str, help='sample name')
    p.add_argument('--vcf', metavar='VCF_FILE', dest='vcf_files', nargs='+',
                   required=True,
                   help='file in VCF 4.1 format to import variants from')
    p.add_argument('--bed', metavar='BED_FILE', dest='bed_files', nargs='+',
                   required=False, default=[],
                   help='file in BED format to import covered regions from')
    p.add_argument('-u', '--data-uploaded', dest='data_uploaded',
                   action='store_true', help='data files are already '
                   'uploaded to the server')
    p.add_argument('-s', '--pool-size', dest='pool_size', default=1, type=int,
                   help='number of individuals in sample (default: 1)')
    p.add_argument('-p', '--public', dest='public', action='store_true',
                   help='sample data is public')
    # Note: We prefer to explicitely include the --no-coverage-profile instead
    #     of concluding it from an empty list of BED files. This prevents
    #     accidentally forgetting the coverage profile.
    p.add_argument('--no-coverage-profile', dest='no_coverage_profile',
                   action='store_true', help='sample has no coverage profile')

    p = subparsers.add_parser('show-sample', help='show sample details',
                              description=show_sample.__doc__.split('\n\n')[0],
                              parents=[config_parser])
    p.set_defaults(func=show_sample)
    p.add_argument('uri', metavar='URI', type=str, help='sample URI')

    p = subparsers.add_parser('add-user', help='add new API user',
                              description=add_user.__doc__.split('\n\n')[0],
                              parents=[config_parser])
    p.set_defaults(func=add_user)
    p.add_argument('login', metavar='LOGIN', type=str, help='user login')
    p.add_argument('password', metavar='PASSWORD', type=str,
                   help='user password')
    p.add_argument('-n', '--name', dest='name', type=str,
                   help='real name (default: login)')
    p.add_argument('--admin', dest='role_admin', action='store_true',
                   help='user has admin role')
    p.add_argument('--importer', dest='role_importer', action='store_true',
                   help='user has importer role')
    p.add_argument('--annotator', dest='role_annotator', action='store_true',
                   help='user has annotator role')
    p.add_argument('--trader', dest='role_trader', action='store_true',
                   help='user has trader role')

    p = subparsers.add_parser('show-user', help='show user details',
                              description=show_sample.__doc__.split('\n\n')[0],
                              parents=[config_parser])
    p.set_defaults(func=show_user)
    p.add_argument('uri', metavar='URI', type=str, help='user URI')

    args = parser.parse_args()

    try:
        args.func(**{k: v for k, v in vars(args).items()
                     if k not in ('func', 'subcommand')})
    except UnauthorizedError:
        abort('Authentication is needed, please make sure you have the '
              'correct login and password defined in "%s"'
              % (args.config or config.USER_CONFIGURATION))
    except ForbiddenError:
        abort('Sorry, you do not have permission')
    except BadRequestError as (code, message):
        abort(message)


if __name__ == '__main__':
    main()
