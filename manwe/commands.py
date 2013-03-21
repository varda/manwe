# -*- coding: utf-8 -*-
"""
Manwë command line interface.

Todo: Move some of the docstring from the _old_population_study.py file here.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import sys

import argparse

from .session import Session


def fatal_error(message):
    sys.stderr.write(message + '\n')
    sys.exit(1)


def import_sample(name, pool_size=1, public=False, coverage_profile=True,
                  vcf_files=None, bed_files=None, config=None):
    """
    Add sample and import variantion and coverage files.
    """
    vcf_files = vcf_files or []
    bed_files = bed_files or []

    if pool_size < 1:
        fatal_error('Pool size should be at least 1')

    if coverage_profile and not bed_files:
        fatal_error('Expected at least one BED file')

    session = Session(config=config)

    sample = session.add_sample(name, pool_size=pool_size,
                                coverage_profile=coverage_profile,
                                public=public)

    for vcf_file in vcf_files:
        data_source = session.add_data_source(
            'Variants from file "%s"' % vcf_file.name,
            filetype='vcf',
            gzipped=vcf_file.name.endswith('.gz'),
            data=vcf_file)
        session.add_variation(sample, data_source)

    for bed_file in bed_files:
        data_source = session.add_data_source(
            'Regions from file "%s"' % bed_file.name,
            filetype='bed',
            gzipped=vcf_file.name.endswith('.gz'),
            data=bed_file)
        session.add_coverage(sample, data_source)


def show_sample(uri, config=None):
    """
    Show sample details.
    """
    session = Session(config=config)
    sample = session.sample(uri)

    print 'Sample: %s' % sample.name


if __name__ == '__main__':
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument('--config', metavar='CONFIG_FILE', type=str,
                               dest='config', help='path to configuration file '
                               'to use instead of looking in default locations')

    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                     parents=[config_parser])

    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    p = subparsers.add_parser('import', help='import sample data',
                              description=import_sample.__doc__.split('\n\n')[0],
                              parents=[config_parser])
    p.add_argument('name', metavar='NAME', type=str, help='sample name')
    p.add_argument('--vcf', metavar='VCF_FILE', type=argparse.FileType('r'),
                   dest='vcf_files', nargs='+', required=True,
                   help='file in VCF 4.1 format to import variants from')
    p.add_argument('--bed', metavar='BED_FILE', type=argparse.FileType('r'),
                   dest='bed_files', nargs='+', required=False,
                   help='file in BED format to import covered regions from')
    p.add_argument('-s', '--pool-size', dest='pool_size', default=1, type=int,
                   help='number of individuals in sample (default: 1)')
    p.add_argument('-p', '--public', dest='public', action='store_true',
                   help='Sample data is public')
    # Note: We prefer to explicitely include the --no-coverage-profile instead
    #     of concluding it from an empty list of BED files. This prevents
    #     accidentally forgetting the coverage profile.
    p.add_argument('--no-coverage-profile', dest='no_coverage_profile',
                   action='store_true', help='Sample has no coverage profile')

    p = subparsers.add_parser('sample', help='show sample details',
                              description=show_sample.__doc__.split('\n\n')[0],
                              parents=[config_parser])
    p.add_argument('uri', metavar='URI', type=str, help='sample URI')

    args = parser.parse_args()

    if args.subcommand == 'import':
        import_sample(args.name, pool_size=args.pool_size, public=args.public,
                      coverage_profile=not args.no_coverage_profile,
                      vcf_files=args.vcf_files, bed_files=args.bed_files,
                      config=args.config)

    if args.subcommand == 'sample':
        show_sample(args.uri, config=args.config)
