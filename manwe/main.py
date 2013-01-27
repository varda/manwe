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

Todo: Handle requests.exceptions.ConnectionError

Copyright (c) 2011 Martijn Vermaat <m.vermaat.hg@lumc.nl>
"""


import sys
from time import sleep

import argparse
import requests
from requests import codes
import simplejson as json

from varda import API, USER, PASSWORD, POLL_SLEEP, MAX_POLLS


def get(location, *args, **kwargs):
    """
    Make a HTTP GET request to the server.

    This is just a convenience wrapper for requests.get where we prepend the
    API root to the requested location and add HTTP Basic Authentication.
    """
    kwargs['auth'] = (USER, PASSWORD)
    if location.startswith('/'):
        location = API + location
    return requests.get(location, *args, **kwargs)


def post(location, *args, **kwargs):
    """
    Make a HTTP POST request to the server.

    This is just a convenience wrapper for requests.get where we prepend the
    API root to the requested location and add HTTP Basic Authentication.
    """
    kwargs['auth'] = (USER, PASSWORD)
    if location.startswith('/'):
        location = API + location
    return requests.post(location, *args, **kwargs)


def patch(location, *args, **kwargs):
    """
    Make a HTTP PATCH request to the server.

    This is just a convenience wrapper for requests.patch where we prepend the
    API root to the requested location and add HTTP Basic Authentication.
    """
    kwargs['auth'] = (USER, PASSWORD)
    if location.startswith('/'):
        location = API + location
    return requests.patch(location, *args, **kwargs)


def fatal_error(message):
    sys.stderr.write(message + '\n')
    sys.exit(1)


def response_error(response):
    try:
        error = json.loads(response.content)['error']
        fatal_error(error['message'])
    except (KeyError, json.JSONDecodeError):
        fatal_error('Got unexpected response from server')


def import_sample(name, vcf_files=None, bed_files=None, coverage_threshold=8,
                  pool_size=1, public=False, annotate=False):
    """
    Add sample and import variants and regions. Optionally annotate.
    """
    vcf_files = vcf_files or []
    bed_files = bed_files or []

    if len(vcf_files) < 1:
        fatal_error('Expecting at least one VCF file')

    if len(bed_files) not in (0, pool_size):
        fatal_error('Expecting either 0 or %d BED files' % pool_size)

    sample_uri = add_sample(name, coverage_threshold=coverage_threshold,
                            pool_size=pool_size, public=public,
                            coverage_profile=bool(bed_files))
    sample = get_sample(sample_uri)

    data_source_uris = []

    for vcf_file in vcf_files:
        data_source_uri, _ = import_vcf(sample['variations'], vcf_file)
        data_source_uris.append(data_source_uri)

    for bed_file in bed_files:
        import_bed(sample['coverages'], bed_file)

    activate_sample(sample_uri)

    if not annotate:
        return

    for i, data_source_uri in enumerate(data_source_uris):
        annotation_uri = annotate_data_source(data_source_uri)
        annotation = get_annotation(annotation_uri)
        data_source_uri = annotation['annotated_data_source']
        data_source = get_data_source(data_source_uri)
        response = get(data_source['data'])
        filename = '/tmp/%s.vcf.gz' % i
        open(filename, 'w').write(response.content)
        print 'Written annotation: %s' % filename


def get_sample(sample_uri):
    """
    Get sample info.
    """
    response = get(sample_uri)

    try:
        sample = json.loads(response.content)['sample']
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    return sample


def get_data_source(data_source_uri):
    """
    Get data source info.
    """
    response = get(data_source_uri)

    try:
        data_source = json.loads(response.content)['data_source']
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    return data_source


def get_annotation(annotation_uri):
    """
    Get annotation info.
    """
    response = get(annotation_uri)

    try:
        annotation = json.loads(response.content)['annotation']
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    return annotation


def activate_sample(sample_uri):
    """
    Activate sample.
    """
    data = {'active': True}
    response = patch(sample_uri, data=data)

    try:
        sample = json.loads(response.content)['sample']
    except (KeyError, json.JSONDecodeError):
        response_error(response)

    print 'Activated sample: %s' % sample_uri
    return sample


def add_sample(name, coverage_threshold=8, pool_size=1, public=False, coverage_profile=True):
    """
    Add sample to the database.
    """
    if pool_size < 1:
        fatal_error('Pool size should be at least 1')

    data = {'name': name,
            'coverage_threshold': coverage_threshold,
            'pool_size': pool_size,
            'public': public,
            'coverage_profile': coverage_profile}
    response = post('/samples', data=data)

    if response.status_code != codes.created:
        response_error(response)

    sample_uri = json.loads(response.content)['sample']

    print 'Added sample to the database: %s' % sample_uri
    return sample_uri


def import_vcf(variations_uri, vcf):
    """
    Import variants from VCF file.
    """
    data = {'name': 'variants', 'filetype': 'vcf'}
    files = {'data': vcf}
    response = post('/data_sources', data=data, files=files)

    if response.status_code != codes.created:
        response_error(response)

    data_source_uri = json.loads(response.content)['data_source']

    print 'Uploaded VCF: %s' % data_source_uri

    data = {'data_source': data_source_uri}
    response = post(variations_uri, data=data)

    if response.status_code != codes.accepted:
        response_error(response)

    status_uri = json.loads(response.content)['variation_import_status']

    print 'Started VCF import: %s' % status_uri

    for _ in range(MAX_POLLS):
        response = get(status_uri)

        if response.status_code != codes.ok:
            response_error(response)

        status = json.loads(response.content)['status']
        if status['ready']:
            print 'Imported VCF: %s' % status['variation']
            return data_source_uri, status['variation']
        else:
            print 'Percentage: %s' % status['percentage']

        sleep(POLL_SLEEP)

    sys.stderr.write('Importing VCF did not finish in time\n')
    sys.exit(1)


def import_bed(coverages_uri, bed):
    """
    Import regions from BED file.
    """
    data = {'name': 'regions', 'filetype': 'bed'}
    files = {'data': bed}
    response = post('/data_sources', data=data, files=files)

    if response.status_code != codes.created:
        response_error(response)

    data_source_uri = json.loads(response.content)['data_source']

    print 'Uploaded BED: %s' % data_source_uri

    data = {'data_source': data_source_uri}
    response = post(coverages_uri, data=data)

    if response.status_code != codes.accepted:
        response_error(response)

    status_uri = json.loads(response.content)['coverage_import_status']

    print 'Started BED import: %s' % status_uri

    for _ in range(MAX_POLLS):
        response = get(status_uri)

        if response.status_code != codes.ok:
            response_error(response)

        status = json.loads(response.content)['status']
        if status['ready']:
            print 'Imported BED: %s' % status['coverage']
            return data_source_uri, status['coverage']

        sleep(POLL_SLEEP)

    sys.stderr.write('Importing BED did not finish in time\n')
    sys.exit(1)


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


def annotate_data_source(data_source_uri):
    """
    Annotate an uploaded data source.
    """
    data_source = get_data_source(data_source_uri)

    response = post(data_source['annotations'])

    if response.status_code != codes.accepted:
        response_error(response)

    status_uri = json.loads(response.content)['annotation_write_status']

    print 'Started VCF annotation: %s' % status_uri

    for _ in range(MAX_POLLS):
        response = get(status_uri)

        if response.status_code != codes.ok:
            response_error(response)

        status = json.loads(response.content)['status']
        if status['ready']:
            print 'Annotated VCF: %s' % status['annotation']
            return status['annotation']

        sleep(POLL_SLEEP)

    sys.stderr.write('Annotating VCF did not finish in time\n')
    sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand',
                                       help='subcommand help')

    p = subparsers.add_parser('import', help='import sample data')
    p.add_argument('name', metavar='NAME', type=str, help='sample name')
    p.add_argument('--vcf', metavar='VCF_FILE', type=argparse.FileType('r'),
                   dest='vcf_files', action='append',
                   help='file in VCF 4.1 format to import variants from (multiple allowed)')
    p.add_argument('--bed', metavar='BED_FILE', type=argparse.FileType('r'),
                   dest='bed_files', action='append',
                   help='file in BED format to import covered regions from (multiple allowed)')
    p.add_argument('-c', dest='coverage_threshold', default=8, type=int,
                   help='coverage threshold for variant calls (default: 8)')
    p.add_argument('-s', dest='pool_size', default=1, type=int,
                   help='number of individuals in sample (default: 1)')
    p.add_argument('-p', '--public', dest='public', action='store_true',
                   help='Sample data is public')
    p.add_argument('-a', '--annotate', dest='annotate', action='store_true',
                   help='Annotate variants')

    p = subparsers.add_parser('show', help='show sample')
    p.add_argument('sample_id', metavar='SAMPLE_ID', type=int, help='sample id')

    p = subparsers.add_parser('list', help='list samples')

    args = parser.parse_args()

    if args.subcommand == 'import':
        import_sample(args.name, vcf_files=args.vcf_files, bed_files=args.bed_files,
                      coverage_threshold=args.coverage_threshold, pool_size=args.pool_size,
                      public=args.public, annotate=args.annotate)

    if args.subcommand == 'show':
        show_sample(args.sample_id)

    if args.subcommand == 'list':
        list_samples()
