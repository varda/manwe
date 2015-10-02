# -*- coding: utf-8 -*-
"""
Manwë sessions.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import collections
import json
import logging
import urlparse

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

from .config import Config
from .errors import (ApiError, BadRequestError, ForbiddenError,
                     NotAcceptableError, NotFoundError, UnauthorizedError,
                     UnsatisfiableRangeError)
from . import resources


ACCEPT_VERSION = '>=2.1.0,<3.0.0'


logger = logging.getLogger('manwe')


def stringify(value):
    """
    Serialize `value` to a `str` parsable by Varda.

    Only works one level deep, so no nesting of structured data.

        >>> stringify(34)
        '34'
        >>> stringify(False)
        'false'
        >>> stringify([4,2,6])
        '4,2,6'
        >>> stringify({'a': False, 'b': True})
        'a:false,b:true'
    """
    if isinstance(value, basestring):
        return value
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, collections.Mapping):
        return ','.join('%s:%s' % (v, stringify(value[v])) for v in value)
    if isinstance(value, collections.Iterable):
        return ','.join(stringify(v) for v in value)
    return str(value)


class SessionMeta(type):
    def __new__(cls, name, parents, attributes):
        """
        Create a new class with API call methods for all collections.

        The class should have a dictionary of resources in its `_collections`
        attribute and generic API call methods `_get_resource`,
        `_get_collection`, and `_create_resource`.
        """
        for key, collection_class in attributes['_collections'].items():
            attributes.update(
                cls._create_collection_methods(key, collection_class))

        return super(SessionMeta, cls).__new__(cls, name, parents, attributes)

    @staticmethod
    def _create_collection_methods(key, collection_class):
        """
        Set API call methods on this session.

        We explicitely register these methods instead of dynamic dispatching
        with `__getattr__`. This enables tab completion and `dir()` without
        having to implement `__dir__`. We can also attach docstrings this way.
        """
        def get_resource(self, uri):
            """
            Get a resource of type {key}.

            :arg str uri: URI for the {key} to retrieve.

            :return: A resource of type {key}.
            :rtype: :class:`.{collection_class.resource_class.__name__}`
            """
            return self._get_resource(key, uri)
        get_resource.__doc__ = get_resource.__doc__.format(
            key=key, collection_class=collection_class)

        def get_collection(self, *args, **kwargs):
            return self._get_collection(key, *args, **kwargs)
        get_collection.__doc__ = collection_class.__init__.__doc__

        def create_resource(self, *args, **kwargs):
            return self._create_resource(key, *args, **kwargs)
        create_resource.__doc__ = collection_class.resource_class.create.__doc__

        return {key: get_resource,
                '%ss' % key: get_collection,
                'create_%s' % key: create_resource}


class AbstractSession(object):
    """
    Abstract session for interfacing the server API.

    Subclasses should have a dictionary of resources in their `_collections`
    attribute.
    """
    __metaclass__ = SessionMeta
    _collections = {}

    def __init__(self, api_root=None, token=None, config=None,
                 log_level=logging.INFO):
        """
        Create a session.

        :arg api_root: Varda API root endpoint.
        :type api_root: str
        :arg token: Varda API authentication token.
        :type token: str
        :arg config: Manwë configuration object (`api_root` and `token` take
           precedence).
        :type config: config.Config
        :arg log_level: Control the level of log messages you will see. Use
          `log_level=logging.DEBUG` to troubleshoot.
        :type log_level: logging.LOG_LEVEL
        """
        self.config = config or Config()

        if api_root:
            self.config.API_ROOT = api_root
        if token:
            self.config.TOKEN = token

        self.set_log_level(log_level)
        self._api_errors = collections.defaultdict(
            lambda: ApiError, {400: BadRequestError,
                               401: UnauthorizedError,
                               403: ForbiddenError,
                               404: NotFoundError,
                               406: NotAcceptableError,
                               416: UnsatisfiableRangeError})
        self.endpoints = self._lookup_endpoints()

    def set_log_level(self, log_level):
        """
        Control the level of log messages you will see.
        """
        logger.setLevel(log_level)

    def _lookup_endpoints(self):
        """
        Dictionary mapping API endpoints to their URIs.
        """
        # TODO: Is API root actually a singleton resource and should we
        #   model it as such and query it as such?
        keys = {key + '_collection' for key in self._collections}
        keys.add('authentication')
        keys.add('genome')
        response = self.get(self.config.API_ROOT).json()
        return {key: response['root'][key]['uri'] for key in keys}

    def _qualified_uri(self, uri):
        return urlparse.urljoin(self.config.API_ROOT, uri)

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
        if 'files' in kwargs:
            # If the `files` keyword argument is set, we don't encode the
            # `data` argument as JSON, since that cannot be combined with a
            # file upload. The consequence is that we cannot have arbitrarily
            # nested or structured data in the `data` argument, only data that
            # can be stringified.
            # We assume files can be large. Unfortunately, the requests
            # library can only do `multipart/form-data` requests by reading
            # the entire files in memory. The requests toolbelt library allows
            # us to stream such requests.
            # https://github.com/sigmavirus24/requests-toolbelt
            def get_filename(handle, default=None):
                if not hasattr(handle, 'name') or handle.name.startswith('<'):
                    return default
                return handle.name
            fields = {k: stringify(v)
                      for k, v in kwargs.get('data', {}).items()}
            fields.update({k: (get_filename(v, k), v)
                           for k, v in kwargs.pop('files', {}).items()})
            encoder = MultipartEncoder(fields=fields)
            kwargs['data'] = encoder
            headers['Content-Type'] = encoder.content_type
        elif 'data' in kwargs:
            kwargs['data'] = json.dumps(kwargs['data'])
            headers['Content-Type'] = 'application/json'
        headers['Accept-Version'] = ACCEPT_VERSION
        #kwargs['auth'] = self.config.USER, self.config.PASSWORD
        if self.config.TOKEN:
            headers['Authorization'] = 'Token ' + self.config.TOKEN
        try:
            response = requests.request(
                method, uri, headers=headers,
                verify=self.config.VERIFY_CERTIFICATE, **kwargs)
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

    def _create_resource(self, key, *args, **kwargs):
        return self._collections[key].resource_class.create(self, *args,
                                                            **kwargs)


class Session(AbstractSession):
    """
    Session for interfacing the server API.

    Example session::

        >>> session = Session()
        >>> sample = session.create_sample('Test')
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
                                       resources.GroupCollection,
                                       resources.SampleCollection,
                                       resources.UserCollection,
                                       resources.VariantCollection,
                                       resources.VariationCollection)}
