# -*- coding: utf-8 -*-
"""
Manwë sessions.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import collections
import functools
import json
import logging
import requests

from .config import Config
from .errors import (ApiError, BadRequestError, ForbiddenError,
                     NotAcceptableError, NotFoundError, UnauthorizedError,
                     UnsatisfiableRangeError)
from . import resources


ACCEPT_VERSION = '>=0.2.0,<0.3.0'


logger = logging.getLogger('manwe')


class Session(object):
    """
    Session for interfacing the server API.

    Example session::

        >>> session = Session()
        >>> sample = session.add_sample('Test')
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
    _collections = {c.key: c for c in (resources.AnnotationCollection,
                                       resources.CoverageCollection,
                                       resources.DataSourceCollection,
                                       resources.SampleCollection,
                                       resources.UserCollection,
                                       resources.VariantCollection,
                                       resources.VariationCollection)}

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
        self._api_errors = collections.defaultdict(
            lambda: ApiError, {400: BadRequestError,
                               401: UnauthorizedError,
                               403: ForbiddenError,
                               404: NotFoundError,
                               406: NotAcceptableError,
                               416: UnsatisfiableRangeError})

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
            keys = {key + '_collection' for key in self._collections}
            keys.add('authentication')
            keys.add('genome')
            response = self.get(self.config.api_root).json()
            self._cached_uris = {key: response[key]['uri'] for key in keys}
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
            kwargs['data'] = json.dumps(kwargs['data'],
                                        cls=resources.ResourceJSONEncoder)
            headers['Content-Type'] = 'application/json'
        headers['Accept-Version'] = ACCEPT_VERSION
        kwargs['auth'] = self.config.user, self.config.password
        try:
            response = requests.request(method, uri, headers=headers, **kwargs)
        except requests.RequestException as e:
            logger.warn('Unable to make API request', method, uri)
            raise
        if response.status_code in (200, 201, 202, 206):
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
        except (KeyError, ValueError):
            code = response.reason
            message = response.text[:78]
        logger.debug('API error code', code, message)
        # Todo: Perhaps also store the response object in the error object?
        # Todo: Sometimes we can be more specific in the exception type
        #     instead of a 1:1 mapping from status codes.
        raise self._api_errors[response.status_code](code, message)

    def _get_resource(self, key, uri):
        response = self.get(uri)
        return self._collections[key].resource_class(self,
                                                     response.json()[key])

    def _get_collection(self, key, *args, **kwargs):
        return self._collections[key](self, *args, **kwargs)

    def _add_resource(self, key, *args, **kwargs):
        return self._collections[key].resource_class.create(self, *args,
                                                            **kwargs)

    def __getattr__(self, name):
        if name in self._collections:
            return functools.partial(self._get_resource, name)
        if name.endswith('s') and name[:-1] in self._collections:
            return functools.partial(self._get_collection, name[:-1])
        if name.startswith('add_') and name[4:] in self._collections:
            return functools.partial(self._add_resource, name[4:])
        raise AttributeError
