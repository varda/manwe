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
from .errors import (ApiError, BadRequestError, ForbiddenError,
                     NotAcceptableError, NotFoundError, UnauthorizedError,
                     UnsatisfiableRangeError)
from . import resources


ACCEPT_VERSION = '>=2.1.0,<3.0.0'


logger = logging.getLogger('manwe')


class Session(object):
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

    def __init__(self, api_root=None, token=None, config=None,
                 log_level=logging.INFO):
        """
        Create a `Session`.

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

        for key in self._collections:
            self._register_calls(key)

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

    def _register_calls(self, key):
        """
        Set API call methods on this session.
        """
        # We explicitely register these methods instead of dynamic dispatching
        # with `__getattr__`. This enables tab completion and `dir()` without
        # having to implement `__dir__`. We can also attach docstrings this
        # way.
        collection_class = self._collections[key]

        def get_resource(uri):
            """
            Get a {key} resource.

            :arg str uri: URI for the {key} to retrieve.
            :return: A {key} resource.
            :rtype: :class:`resources.{collection_class.resource_class.__name__}`
            """
            return self._get_resource(key, uri)
        get_resource.__doc__ = get_resource.__doc__.format(
            key=key, collection_class=collection_class)

        def get_collection(*args, **kwargs):
            """
            Get a {key} resource collection.

            The collection can be filtered by setting any of the following
            keyword args: {accepted_args}

            :return: A {key} resource collection.
            :rtype: :class:`resources.{collection_class.__name__}`
            """
            return self._get_collection(key, *args, **kwargs)
        get_collection.__doc__ = get_collection.__doc__.format(
            key=key, collection_class=collection_class,
            accepted_args=', '.join(collection_class._accepted_args) or 'none')

        def create_resource(*args, **kwargs):
            return self._create_resource(key, *args, **kwargs)
        create_resource.__doc__ = collection_class.resource_class.create.__doc__

        setattr(self, key, get_resource)
        setattr(self, '%ss' % key, get_collection)
        setattr(self, 'create_%s' % key, create_resource)

    def _qualified_uri(self, uri):
        if uri.startswith('/'):
            if self.config.API_ROOT.endswith('/'):
                return self.config.API_ROOT + uri[1:]
            return self.config.API_ROOT + uri
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
        #kwargs['auth'] = self.config.USER, self.config.PASSWORD
        if self.config.TOKEN:
            headers['Authorization'] = 'Token ' + self.config.TOKEN
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

    def _create_resource(self, key, *args, **kwargs):
        return self._collections[key].resource_class.create(self, *args,
                                                            **kwargs)


# TODO: Some kind of session class factory would probably be better. It could
# prepopulate all API call methods, which would also make them available to
# Sphinx class documentation and the like.
# Session = make_session_class(resources.AnnotationCollection,
#                              resources.CoverageCollection,
#                              resources.DataSourceCollection,
#                              resources.GroupCollection,
#                              resources.SampleCollection,
#                              resources.UserCollection,
#                              resources.VariantCollection,
#                              resources.VariationCollection
