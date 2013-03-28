# -*- coding: utf-8 -*-
"""
Manwë sessions.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import collections
import json
import logging
import requests

from .config import Config
from .errors import (ApiError, BadRequestError, UnauthorizedError,
                     ForbiddenError, NotFoundError)
from . import resources


logger = logging.getLogger('manwe')


class Session(object):
    """
    Session for interfacing the server API.

    Example session::

        >>> session = Session()
        >>> sample = add_sample('Test')
        >>> sample.uri
        '/samples/1'
        >>> sample.dirty
        False
        >>> sample.name = 'Test sample'
        >>> sample.dirty
        True
        >>> sample.save()
        >>> sample.dirty
        False
    """
    def __init__(self, api_root=None, user=None, password=None, config=None,
                 log_level=logging.INFO):
        """
        Create a `Session`.

        :arg str config: Configuration filename.
        :arg logging.LOG_LEVEL log_level: Control the level of log messages
            you will see. Use `log_level=logging.DEBUG` to troubleshoot.
        """
        self.config = Config(filename=config, api_root=api_root, user=user,
                             password=password)
        self.set_log_level(log_level)
        self._cached_uris = None
        self._api_errors = collections.defaultdict(lambda: ApiError,
                                                   {400: BadRequestError,
                                                    401: UnauthorizedError,
                                                    403: ForbiddenError,
                                                    404: NotFoundError})

    def set_log_level(self, log_level):
        """
        Control the level of log messages you will see.
        """
        logger.setLevel(log_level)

    @property
    def uris(self):
        """
        Dictionary mapping API endpoints to their URIs.
        """
        if not self._cached_uris:
            response = self.get(self.config.api_root).json()
            self._cached_uris = {key: response[key + '_uri'] for key in
                                 ('authentication', 'users', 'samples',
                                  'variations', 'coverages', 'data_sources',
                                  'annotations', 'variants')}
        return self._cached_uris

    def _qualified_uri(self, uri):
        if uri.startswith('/'):
            if self.config.api_root.endswith('/'):
                return self.config.api_root + uri[1:]
            return self.config.api_root + uri
        return uri

    def get(self, *args, **kwargs):
        """
        Short for :meth:`request` where `method` is ``GET``.
        """
        return self.request('GET', *args, **kwargs)

    def post(self, *args, **kwargs):
        """
        Short for :meth:`request` where `method` is ``POST``.
        """
        return self.request('POST', *args, **kwargs)

    def patch(self, *args, **kwargs):
        """
        Short for :meth:`request` where `method` is ``PATCH``.
        """
        return self.request('PATCH', *args, **kwargs)

    def request(self, method, uri, **kwargs):
        """
        Send HTTP request to server.

        :raises requests.RequestException: Exception occurred while handling
            an API request.
        """
        # Note: If the `files` keyword argument is set, we don't encode the
        #     `data` argument as JSON, since that cannot be combined with a
        #     file upload. The consequence is that we cannot have nested or
        #     structured data in the `data` argument.
        headers = kwargs.pop('headers', {})
        uri = self._qualified_uri(uri)
        if 'data' in kwargs and not 'files' in kwargs:
            kwargs['data'] = json.dumps(kwargs['data'])
            headers['content-type'] = 'application/json'
        kwargs['auth'] = self.config.user, self.config.password
        if headers:
            kwargs['headers'] = headers
        try:
            response = requests.request(method, uri, **kwargs)
        except requests.RequestException as e:
            logger.warn('Unable to make API request', method, uri)
            raise
        if response.status_code in (200, 201, 202):
            # Todo: What if no JSON?
            logger.debug('Successful API response', method, uri,
                         response.status_code)
            return response
        logger.warn('Error API response', method, uri, response.status_code)
        self._response_error(response)

    def _response_error(self, response):
        try:
            content = response.json()
            code = content['error']['code']
            message = content['error']['message']
        except KeyError, ValueError:
            code = response.reason
            message = response.text[:78]
        logger.debug('API error code', code, message)
        raise self._api_errors[response.status_code](code, message)

    def annotation(self, uri):
        """
        Get an annotation resource by URI.
        """
        response = self.get(uri)
        return resources.Annotation(self, response.json()['annotation'])

    def coverage(self, uri):
        """
        Get a coverage resource by URI.
        """
        response = self.get(uri)
        return resources.Coverage(self, response.json()['coverage'])

    def data_source(self, uri):
        """
        Get a data source resource by URI.
        """
        response = self.get(uri)
        return resources.DataSource(self, response.json()['data_source'])

    def sample(self, uri):
        """
        Get a sample resource by URI.
        """
        response = self.get(uri)
        return resources.Sample(self, response.json()['sample'])

    def user(self, uri):
        """
        Get a user resource by URI.
        """
        response = self.get(uri)
        return resources.User(self, response.json()['user'])

    def variant(self, uri):
        """
        Get a variant resource by URI.
        """
        response = self.get(uri)
        return resources.Variant(self, response.json()['variant'])

    def variation(self, uri):
        """
        Get a variation resource by URI.
        """
        response = self.get(uri)
        return resources.Variation(self, response.json()['variation'])

    def annotations(self):
        """
        Returns a :class:`AnnotationCollection` instance.
        """
        return resources.AnnotationCollection(self)

    def coverages(self):
        """
        Returns a :class:`CoverageCollection` instance.
        """
        return resources.CoverageCollection(self)

    def data_sources(self):
        """
        Returns a :class:`DataSourceCollection` instance.
        """
        return resources.DataSourceCollection(self)

    def samples(self):
        """
        Returns a :class:`SampleCollection` instance.
        """
        return resources.SampleCollection(self)

    def users(self):
        """
        Returns a :class:`UserCollection` instance.
        """
        return resources.UserCollection(self)

    def variants(self):
        """
        Returns a :class:`VariantCollection` instance.
        """
        return resources.VariantCollection(self)

    def variations(self):
        """
        Returns a :class:`VariationCollection` instance.
        """
        return resources.VariationCollection(self)

    def add_annotation(self, data_source, global_frequency=True,
                       sample_frequency=None):
        """
        Create a new annotation resource.
        """
        sample_frequency = sample_frequency or []

        data = {'data_source': data_source.uri,
                'global_frequency': global_frequency,
                'sample_frequency': [sample.uri for sample in sample_frequency]}
        response = self.post(self.uris['annotations'], data=data)
        return self.annotation(response.json()['annotation_uri'])

    def add_coverage(self, sample, data_source):
        """
        Create a new coverage resource.
        """
        data = {'sample': sample.uri,
                'data_source': data_source.uri}
        response = self.post(self.uris['coverages'], data=data)
        return self.coverage(response.json()['coverage_uri'])

    def add_data_source(self, name, filetype, gzipped=False, data=None,
                        local_file=None):
        """
        Create a new sample resource.
        """
        post_data = {'name': name,
                     'filetype': filetype,
                     'gzipped': gzipped}
        if local_file:
            post_data.update(local_file=local_file)
        if data is None:
            files = None
        else:
            files = {'data': data}
        response = self.post(self.uris['data_sources'], data=post_data,
                             files=files)
        return self.data_source(response.json()['data_source_uri'])

    def add_sample(self, name, pool_size=1, coverage_profile=True,
                   public=False):
        """
        Create a new sample resource.
        """
        data = {'name': name,
                'pool_size': pool_size,
                'coverage_profile': coverage_profile,
                'public': public}
        response = self.post(self.uris['samples'], data=data)
        return self.sample(response.json()['sample_uri'])

    def add_user(self, login, password, name=None, roles=None):
        """
        Create a new user resource.
        """
        data = {'login': login,
                'password': password,
                'name': name or login,
                'roles': roles or []}
        response = self.post(self.uris['users'], data=data)
        return self.user(response.json()['user_uri'])

    def add_variant(self, chromosome, position, reference='', observed=''):
        """
        Create a new variant resource.
        """
        data = {'chromosome': chromosome,
                'position': position,
                'reference': reference,
                'observed': observed}
        response = self.post(self.uris['variants'], data=data)
        return self.variant(response.json()['variant_uri'])

    def add_variation(self, sample, data_source, skip_filtered=True,
                      use_genotypes=True, prefer_genotype_likelihoods=False):
        """
        Create a new variation resource.
        """
        data = {'sample': sample.uri,
                'data_source': data_source.uri,
                'skip_filtered': skip_filtered,
                'use_genotypes': use_genotypes,
                'prefer_genotype_likelihoods': prefer_genotype_likelihoods}
        response = self.post(self.uris['variations'], data=data)
        return self.variation(response.json()['variation_uri'])
