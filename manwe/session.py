# -*- coding: utf-8 -*-
"""
Manwë sessions.
"""


import collections
import json
import logging
import requests

from .config import Config
from .errors import (ApiError, BadRequestError, UnauthorizedError,
                     ForbiddenError, NotFoundError)
from .resources import Sample, SampleCollection, User


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
        headers = kwargs.pop('headers', {})
        uri = self._qualified_uri(uri)
        if 'data' in kwargs:
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

    def get_sample(self, uri):
        """
        Get a sample by URI.
        """
        response = self.get(uri)
        return Sample(self, response.json()['sample'])

    def get_user(self, uri):
        """
        Get a user by URI.
        """
        response = self.get(uri)
        return User(self, response.json()['user'])

    def list_samples(self):
        """
        Returns a :class:`SampleCollection` instance.
        """
        return SampleCollection(self)

    def add_sample(self, name, pool_size=1, coverage_profile=True,
                   public=False):
        """
        Create a new sample.
        """
        data = {'name': name,
                'pool_size': pool_size,
                'coverage_profile': coverage_profile,
                'public': public}
        response = self.post(self.uris['samples'], data=data)
        return self.get_sample(response.json()['sample_uri'])

    def add_user(self, login, password, name=None, roles=None):
        """
        Create a new user.
        """
        data = {'login': login,
                'password': password,
                'name': name or login,
                'roles': roles or []}
        response = self.post(self.uris['users'], data=data)
        return self.get_user(response.json()['user_uri'])
