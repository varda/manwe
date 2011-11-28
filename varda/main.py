#!/usr/bin/env python
"""
Import population study in the variant database from VCF files.

Expects a file in VCF version 4.1 format with merged genotype information for
all samples in the study. For example (INFO column data is not shown):

    1 10132 . T A,C 67 PASS INFO GT ./. 0/1 ./. 2/2 ./. 1/2 0/2
    1 10134 . A C   37 PASS INFO GT ./. ./. ./. 0/1 1/1 ./. ./.

Variant support is defined by the number of samples in which a variant allele
was called, ignoring homo-/heterozygocity. Quality scores and INFO column data
are ignored.

The example lines above would yield three variant observations:
- chr1:10132 T>A with support 2
- chr1:10132 T>C with support 3
- chr1:10134 A>C with support 2

The reason for using the full merged VCF files with genotype data? The trick
here is to just count the number of individuals with a variant called, as
opposed to the number of variant alleles called. The latter may be higher and
is typically the only value that can be obtained from merged VCF files without
genotype data (true for GoNL SNPs and 1KG variants; GoNL INDELs don't even
have genotype data to start with).

Calculating variant support from genotypes can be disabled with the -n option.
In that case, the number of names in the 'SF' info field is used. If the field
is not present, the value of the 'AC' info field is used.

Genome of the Netherlands example usage:

    ./population_study.py add -p 500 -c 'Genome of the Netherlands' -v 'BGI variant calls'
    ./population_study.py import 1 merged20110920.vcf   # SNP
    ./population_study.py import -n 1 merged.indel.vcf  # INDEL

1000 Genomes example usage:

    ./population_study.py add -p 1092 -c '1000 Genomes' -v 'October 2011 Integrated Variant Set'
    # Get ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20110521/*.vcf.gz
    for VCF in *.vcf.gz; do
        zcat $VCF | ./population_study.py import 2 -
    done

Importing already existing observations is not handled at the moment. So if
an imported VCF is imported again, all variants will have two observations
with the same support. A future version should give the option to either
overwrite the existing observation (but is this useful? you only re-import if
you know your data has changed and in that case some old observations will not
be removed) or to update the support value for the existing observation (e.g.
if you get data for additional samples in you study).

Todo: Sample.pipeline_v column should allow longer strings.
Todo: Option to overwrite/increment existing observations.

Copyright (c) 2011 Martijn Vermaat <m.vermaat.hg@lumc.nl>
"""


import sys

import argparse
import requests
import simplejson as json

from varda import SERVER_ROOT


def add_sample(name, pool_size=1):
    """
    Add sample to the database.
    """
    data={'name': name, 'pool_size': pool_size}
    r = requests.post(SERVER_ROOT + '/samples', data)
    #print 'Added sample to the database with sample id %d' % sample_id
    print r.content


def remove_sample(sample_id, only_variants=False):
    """
    Remove sample from the database.
    """
    db = Db.NGSDb()
    sample = db.getSample(sample_id)

    if not sample:
        sys.stderr.write('No sample with sample id %d\n' % sample_id)
        sys.exit(1)

    db.deleteSample(sample_id, only_variants)
    if only_variants:
        print 'Removed variant observations from the database with sample id %d' % sample_id
    else:
        print 'Removed sample from the database with sample id %d' % sample_id


def list_samples():
    """
    List samples in the database.
    """
    r = requests.get(SERVER_ROOT + '/samples')
    print '  id  pool size  name'
    for sample in json.loads(r.content)['samples']:
        print '%4.i  %9.i  %s' % (sample['id'], sample['pool_size'], sample['name'])


def show_sample(sample_id):
    """
    Show information on a sample.
    """
    r = requests.get(SERVER_ROOT + '/samples/' + str(sample_id))

    if r.status_code == requests.codes.ok:
        sample = json.loads(r.content)['sample']
        print 'Sample id:  %d' % sample['id']
        print 'Date added: %s' % sample['added']
        print 'Name:       %s' % sample['name']
        print 'Poolsize:   %s' % sample['pool_size']
    else:
        sys.stderr.write('No sample with sample id %d\n' % sample_id)
        sys.exit(1)


def import_vcf(sample_id, vcf, name, use_genotypes=True):
    """
    Import variants from VCF file.
    """
    data = {'name': name}
    files = {'data': vcf}
    r = requests.post(SERVER_ROOT + '/data_sources', data=data, files=files)
    print r.headers['location']
    r = requests.get(r.headers['location'])
    print r.content
    data_source = json.loads(r.content)['data_source']
    data = {'data_source': data_source['id']}
    r = requests.post(SERVER_ROOT + '/samples/' + str(sample_id) + '/observations', data=data)
    poll_location = r.headers['location']
    while True:
        r = requests.get(poll_location)
        print r.content


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    parser_add = subparsers.add_parser('add', help='add sample')
    group = parser_add.add_argument_group()
    group.add_argument('name', metavar='NAME', type=str, help='sample name')
    parser_add.add_argument('-p', dest='pool_size', default=1, type=int,
                        help='number of individuals in sample (default: 1)')

    parser_show = subparsers.add_parser('show', help='show sample')
    group = parser_show.add_argument_group()
    group.add_argument('sample_id', metavar='SAMPLE_ID', type=int,
                       help='sample id')

    parser_list = subparsers.add_parser('list', help='list samples')

    #parser_remove = subparsers.add_parser('remove',
    #                                      help='remove population study')
    #group = parser_remove.add_argument_group()
    #group.add_argument('sample_id', metavar='SAMPLE_ID', type=int,
    #                   help='population study sample id')
    #parser_remove.add_argument('-o', '--only-variants', dest='only_variants',
    #                           action='store_true',
    #                           help='don\t remove the study, only its variants')

    parser_import = subparsers.add_parser('import', help='import variants')
    group = parser_import.add_argument_group()
    group.add_argument('sample_id', metavar='SAMPLE_ID', type=int,
                       help='sample id')
    group.add_argument('vcf', metavar='VCF_FILE', type=argparse.FileType('r'),
                       help='file in VCF 4.1 format to import variants from')
    group.add_argument('name', metavar='NAME', type=str, help='data source name')
    parser_import.add_argument('-n', '--no-genotypes', dest='no_genotypes',
                               action='store_true', help='don\'t use genotypes')

    args = parser.parse_args()

    if args.subcommand in ('show', 'remove', 'import') \
           and not 0 < args.sample_id < 100:
            sys.stderr.write('Population studies have sample id < 100\n')
            sys.exit(1)

    if args.subcommand == 'add':
        add_sample(args.name, pool_size=args.pool_size)

    if args.subcommand == 'show':
        show_sample(args.sample_id)

    #if args.subcommand == 'remove':
    #    remove_sample(args.sample_id, args.only_variants)

    if args.subcommand == 'list':
        list_samples()

    if args.subcommand == 'import':
        import_vcf(args.sample_id, args.vcf, args.name, not args.no_genotypes)
