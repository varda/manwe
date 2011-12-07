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
from time import sleep

import argparse
import requests
from requests import codes
import simplejson as json

from varda import API_ROOT, VARDA_USER, VARDA_PASSWORD


def get(location, *args, **kwargs):
    """
    Make a HTTP GET request to the server.

    This is just a convenience wrapper for requests.get where we prepend the
    API root to the requested location and add HTTP Basic Authentication.
    """
    kwargs['auth'] = (VARDA_USER, VARDA_PASSWORD)
    if location.startswith('/'):
        location = API_ROOT + location
    return requests.get(location, *args, **kwargs)


def post(location, *args, **kwargs):
    """
    Make a HTTP POST request to the server.

    This is just a convenience wrapper for requests.get where we prepend the
    API root to the requested location and add HTTP Basic Authentication.
    """
    kwargs['auth'] = (VARDA_USER, VARDA_PASSWORD)
    if location.startswith('/'):
        location = API_ROOT + location
    return requests.post(location, *args, **kwargs)


def response_error(response):
    try:
        error = json.loads(response.content)['error']
        sys.stderr.write('Got error from server: %s\n' % error['message'])
    except (KeyError, json.JSONDecodeError):
        sys.stderr.write('Got unexpected response from server\n')
    sys.exit(1)


def add_sample(name, coverage_threshold=8, pool_size=1):
    """
    Add sample to the database.

    Todo: Handle requests.exceptions.ConnectionError
    """
    data = {'name': name, 'coverage_threshold': coverage_threshold, 'pool_size': pool_size}
    response = post('/samples', data=data)

    if response.status_code != codes.found:
        response_error(response)

    response = get(response.headers['location'])
    sample = json.loads(response.content)['sample']
    print 'Added sample to the database with sample id %d' % sample['id']
    return


#def remove_sample(sample_id, only_variants=False):
#    """
#    Remove sample from the database.
#    """
#    db = Db.NGSDb()
#    sample = db.getSample(sample_id)
#
#    if not sample:
#        sys.stderr.write('No sample with sample id %d\n' % sample_id)
#        sys.exit(1)
#
#    db.deleteSample(sample_id, only_variants)
#    if only_variants:
#        print 'Removed variant observations from the database with sample id %d' % sample_id
#    else:
#        print 'Removed sample from the database with sample id %d' % sample_id


def list_samples():
    """
    List samples in the database.
    """
    response = get('/samples')
    try:
        samples = json.loads(response.content)['samples']
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    print '  id  pool size  name'
    for sample in samples:
        print '%4.i  %9.i  %s' % (sample['id'], sample['pool_size'], sample['name'])


def show_sample(sample_id):
    """
    Show information on a sample.
    """
    response = get('/samples/' + str(sample_id))

    try:
        sample = json.loads(response.content)['sample']
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    print 'Sample id:          %d' % sample['id']
    print 'Date added:         %s' % sample['added']
    print 'Name:               %s' % sample['name']
    print 'Coverage threshold: %s' % sample['coverage_threshold']
    print 'Poolsize:           %s' % sample['pool_size']


def import_vcf(sample_id, vcf, name, use_genotypes=True):
    """
    Import variants from VCF file.
    """
    data = {'name': name, 'filetype': 'vcf'}
    files = {'data': vcf}
    response = post('/data_sources', data=data, files=files)

    if response.status_code != codes.found:
        response_error(response)

    response = get(response.headers['location'])
    data_source = json.loads(response.content)['data_source']

    data = {'data_source': data_source['id']}
    response = post('/samples/' + str(sample_id) + '/observations', data=data)

    if response.status_code != codes.found:
        response_error(response)

    wait_location = response.headers['location']

    while True:
        response = get(wait_location)
        try:
            observations = json.loads(response.content)['observations']
        except (KeyError, json.JSONDecodeError):
            response_error(response)
        if observations['ready']:
            print 'Imported VCF file'
            break
        sleep(3)


def annotate_vcf(vcf, name):
    """
    Annotate variants in a VCF file.
    """
    data = {'name': name, 'filetype': 'vcf'}
    files = {'data': vcf}
    response = post('/data_sources', data=data, files=files)

    if response.status_code != codes.found:
        response_error(response)

    response = get(response.headers['location'])
    data_source = json.loads(response.content)['data_source']

    response = post('/data_sources/' + str(data_source['id']) + '/annotations')

    if response.status_code != codes.found:
        response_error(response)

    wait_location = response.headers['location']

    annotation_id = None

    while True:
        response = get(wait_location)
        try:
            annotation = json.loads(response.content)['annotation']
        except (KeyError, json.JSONDecodeError):
            response_error(response)
        if annotation['ready']:
            annotation_id = annotation['id']
            break
        sleep(3)

    response = get('/data_sources/' + str(data_source['id']) + '/annotations/' + str(annotation_id))

    try:
        #annotation = json.loads(response.content)['annotation']
        sys.stdout.write(response.content)
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    #print 'Annotation id: %d' % annotation['id']
    #print 'Data source    %s' % annotation['data_source']
    #print 'Date added:    %s' % annotation['added']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    parser_add = subparsers.add_parser('add', help='add sample')
    group = parser_add.add_argument_group()
    group.add_argument('name', metavar='NAME', type=str, help='sample name')
    parser_add.add_argument('-c', dest='coverage_threshold', default=8, type=int,
                            help='coverage threshold for variant calls (default: 8)')
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

    parser_annotate = subparsers.add_parser('annotate', help='annotate variants')
    group = parser_annotate.add_argument_group()
    group.add_argument('vcf', metavar='VCF_FILE', type=argparse.FileType('r'),
                       help='file in VCF 4.1 format to annotate variants from')
    group.add_argument('name', metavar='NAME', type=str, help='data source name')

    args = parser.parse_args()

    if args.subcommand in ('show', 'remove', 'import') \
           and not 0 < args.sample_id < 100:
            sys.stderr.write('Population studies have sample id < 100\n')
            sys.exit(1)

    if args.subcommand == 'add':
        add_sample(args.name, coverage_threshold=args.coverage_threshold, pool_size=args.pool_size)

    if args.subcommand == 'show':
        show_sample(args.sample_id)

    #if args.subcommand == 'remove':
    #    remove_sample(args.sample_id, args.only_variants)

    if args.subcommand == 'list':
        list_samples()

    if args.subcommand == 'import':
        import_vcf(args.sample_id, args.vcf, args.name, not args.no_genotypes)

    if args.subcommand == 'annotate':
        annotate_vcf(args.vcf, args.name)
