# -*- coding: utf-8 -*-
"""
Manwë resources.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import collections
import json

import dateutil.parser
import werkzeug.datastructures
import werkzeug.http

from .errors import NotFoundError, UnsatisfiableRangeError


COLLECTION_CACHE_SIZE = 20


class ResourceJSONEncoder(json.JSONEncoder):
    """
    Specialized :class:`json.JSONEncoder` that can encode resources.

    Use like this::

        >>> import json
        >>> user = session.add_user('test', '***')
        >>> json.dumps(user, cls=ResourceJSONEncoder)
        '/users/3'

    """
    def default(self, o):
        if isinstance(o, _Resource):
            return str(o)
        return super(ResourceJSONEncoder, self).default(o)


class _Resource(object):
    """
    Base class for representing server resources.
    """
    # Note: The `_mutable` tuple must always contain at least ``uri``.
    # Note: Any structured fields (such as lists and dicts) defined in
    #     `_mutable`, won't just work with the getters and setters defined
    #     for them automatically below. This is because they can be modified
    #     without touching the setter method.
    #     Example: calling `resource.list_field.append(value)` will not add
    #     the `list_field` to the set of dirty fields.
    #     One solution for this, as implemented for the `roles` field for the
    #     `User` resource, is to have an immutable field value (frozenset in
    #     this case) and define separate methods for updating the field.
    #     Another approach would be something similar to the `MutableDict`
    #     type in SQLAlchemy [1].
    #
    # [1] http://docs.sqlalchemy.org/en/latest/orm/extensions/mutable.html
    _mutable = ()
    _immutable = ()

    def __new__(cls, *args, **kwargs):
        """
        Register getters (and setters) for the list of names defined in the
        `_mutable` and `_immutable` class properties. The corresponding values
        are found in the `_fields` instance variable.
        """
        def getter(name):
            def getter_for_name(self):
                return self._fields.get(name)
            return getter_for_name
        def setter(name):
            def setter_for_name(self, value):
                self._dirty.add(name)
                self._fields[name] = value
            return setter_for_name
        # Note that we only register the getters/setters if the attribute is
        # not yet set. This makes it possible to implement specific behaviours
        # in subclasses by 'overriding' them.
        for name in cls._mutable:
            if not hasattr(cls, name):
                setattr(cls, name, property(getter(name), setter(name)))
        for name in cls._immutable:
            if not hasattr(cls, name):
                setattr(cls, name, property(getter(name)))
        return super(_Resource, cls).__new__(cls, *args, **kwargs)

    def __init__(self, session, fields):
        """
        Create a representation for a server resource.

        :arg session: Manwë session.
        :type session: :class:`manwe.Session`
        :arg fields: Dictionary with field names (the dictionary keys) and
            their values for this resource.
        :type fields: dict
        """
        #: The session this resource is attached to as
        #: :class:`session.Session <Session>`.
        self.session = session
        self._dirty = set()
        self._fields = fields

    # Serialization of values by `urllib.quote_plus` uses `str()` if all else
    # fails. This is used by `urllib.encode`, which in turn is used by
    # `requests.request` to serialize the `data` argument.
    # Implementing `__str__` here effectively means implementing what gets
    # send to the server if we pass a resource with the request.
    # Note that this doesn't work for `json.dumps`, where we really have to
    # implement a `json.JSONEncoder.default` method to serialize resources.
    # For this, a specialized encoder class is provided above as
    # `ResourceJSONEncoder`.
    # Todo: Have a more informative `__repr__` implementation.
    def __str__(self):
        return self._fields['uri']

    @property
    def dirty(self):
        """
        `True` if there are any unsaved changes on this resource, `False`
        otherwise.
        """
        return bool(self._dirty)

    def save(self):
        """
        Save any unsaved changes on this resource.
        """
        if self.dirty:
            self.session.request(self._fields['uri'], method='PATCH',
                                 data={k: self._fields[k] for k in self._dirty})
            self._dirty.clear()
        # Todo: On save, refresh all fields from server.


class _ResourceCollection(object):
    """
    Base class for representing server resource collections, iterators
    returning :class:`_Resource` instances.
    """
    # Index in `Session.uris` for the URI to this collection.
    _collection_uri = None

    # Key in API collection response objects to the list of resources.
    _collection_key = None

    # Names by which the collection can be parameterized.
    _collection_args = ()

    # Resource class to use for instantiating resources in this collection.
    _resource_class = None

    def __init__(self, session, **kwargs):
        """
        Create a representation for a server resource collection.
        """
        #: The session this resource collection  is attached to as
        #: :class:`session.Session <Session>`.
        self.session = session

        #: The total number of resources in this collection as last reported
        #: by the server. Note that the actual number of resources produced by
        #: the collection iterator might deviate from this number, and this is
        #: why there is not `__len__` property defined.
        self.size = 0

        self._args = {arg: kwargs.get(arg) for arg in self._collection_args}
        self._next = 0
        self._resources = collections.deque()
        self._get_resources()

    def __iter__(self):
        return self

    def __getattr__(self, name):
        # This enables us to do `variations.sample` if `variations` is a
        # collection created with a `sample` argument.
        try:
            return self._args[name]
        except KeyError:
            raise AttributeError

    def _get_resources(self):
        if self._next is None:
            return
        # Todo: Use Range object from Werkzeug to construct this header.
        range_ = werkzeug.datastructures.Range(
            'items', [(self._next, self._next + COLLECTION_CACHE_SIZE)])
        try:
            response = self.session.get(self.session.uris[self._collection_uri],
                                        headers={'Range': range_.to_header()},
                                        data=self._args)
        except UnsatisfiableRangeError:
            self.size = 0
            self._next = None
            return
        self._resources.extend(self._resource_class(self.session, resource)
                               for resource in response.json()[self._collection_key])
        content_range = werkzeug.http.parse_content_range_header(
            response.headers['Content-Range'])
        self.size = content_range.length
        if content_range.stop < content_range.length:
            self._next += COLLECTION_CACHE_SIZE
        else:
            self._next = None

    def next(self):
        """
        Return the next :class:`_Resource` in the collection.
        """
        if not self._resources:
            self._get_resources()
        try:
            return self._resources.popleft()
        except IndexError:
            raise StopIteration()

    # Python 3 compatibility.
    __next__ = next


class Annotation(_Resource):
    """
    Base class for representing an annotation resource.
    """
    _immutable = ('uri', 'original_data_source_uri',
                  'annotated_data_source_uri', 'written')

    @property
    def original_data_source(self):
        return self.session.data_source(self.original_data_source_uri)

    @property
    def annotated_data_source(self):
        return self.session.data_source(self.annotated_data_source_uri)


class Coverage(_Resource):
    """
    Base class for representing a coverage resource.
    """
    _immutable = ('uri', 'sample_uri', 'data_source_uri', 'imported')

    @property
    def sample(self):
        return self.session.sample(self.sample_uri)

    @property
    def data_source(self):
        return self.session.data_source(self.data_source_uri)


class DataSource(_Resource):
    """
    Base class for representing a data source resource.
    """
    _mutable = ('name',)
    _immutable = ('uri', 'user_uri', 'data_uri', 'name', 'filetype',
                  'gzipped', 'added')

    @property
    def added(self):
        return dateutil.parser.parse(self._fields['added'])

    @property
    def user(self):
        return self.session.user(self.user_uri)


class Sample(_Resource):
    """
    Base class for representing a sample resource.
    """
    _mutable = ('name', 'pool_size', 'coverage_profile', 'public', 'active')
    _immutable = ('uri', 'user_uri', 'added')

    @property
    def added(self):
        return dateutil.parser.parse(self._fields['added'])

    @property
    def user(self):
        return self.session.user(self.user_uri)


class User(_Resource):
    """
    Base class for representing a user resource.
    """
    # Todo: Should password be an ordinary field (with initial None) value
    #     like it is now? Or should we modify it through some change_password
    #     method?
    _mutable = ('password', 'name', 'roles')
    _immutable = ('uri', 'login', 'added')

    @property
    def added(self):
        return dateutil.parser.parse(self._fields['added'])

    @property
    def roles(self):
        return frozenset(self._fields['roles'])

    @roles.setter
    def roles(self, roles):
        self._dirty.add('roles')
        self._fields['roles'] = list(roles)

    def add_role(self, role):
        self._dirty.add('roles')
        roles = set(self._fields['roles'])
        roles.add(role)
        self._fields['roles'] = list(roles)

    def remove_role(self, role):
        self._dirty.add('roles')
        roles = set(self._fields['roles'])
        roles.remove(role)
        self._fields['roles'] = list(roles)


class Variant(_Resource):
    """
    Base class for representing a variant resource.
    """
    # Todo: The API for this resource has been changed.
    _immutable = ('uri', 'chromosome', 'position', 'reference', 'observed',
                  'global_frequency', 'sample_frequency')


class Variation(_Resource):
    """
    Base class for representing a variation resource.
    """
    _immutable = ('uri', 'sample_uri', 'data_source_uri', 'imported')

    @property
    def sample(self):
        return self.session.sample(self.sample_uri)

    @property
    def data_source(self):
        return self.session.data_source(self.data_source_uri)


class AnnotationCollection(_ResourceCollection):
    """
    Class for representing an annotation resource collection as an iterator
    returning :class:`Annotation` instances.
    """
    _collection_uri = 'annotations'
    _collection_key = 'annotations'
    _resource_class = Annotation


class CoverageCollection(_ResourceCollection):
    """
    Class for representing a coverage resource collection as an iterator
    returning :class:`Coverage` instances.
    """
    _collection_uri = 'coverages'
    _collection_key = 'coverages'
    _resource_class = Coverage


class DataSourceCollection(_ResourceCollection):
    """
    Class for representing a data source resource collection as an iterator
    returning :class:`DataSource` instances.
    """
    _collection_uri = 'data_sources'
    _collection_key = 'data_sources'
    _resource_class = DataSource


class SampleCollection(_ResourceCollection):
    """
    Class for representing a sample resource collection as an iterator
    returning :class:`Sample` instances.
    """
    _collection_uri = 'samples'
    _collection_key = 'samples'
    _collection_args = ('user',)
    _resource_class = Sample


class UserCollection(_ResourceCollection):
    """
    Class for representing a user resource collection as an iterator returning
    :class:`User` instances.
    """
    _collection_uri = 'users'
    _collection_key = 'users'
    _resource_class = User


class VariantCollection(_ResourceCollection):
    """
    Class for representing a variant resource collection as an iterator
    returning :class:`Variant` instances.
    """
    _collection_uri = 'variants'
    _collection_key = 'variants'
    _resource_class = Variant


class VariationCollection(_ResourceCollection):
    """
    Class for representing a variation resource collection as an iterator
    returning :class:`Variation` instances.
    """
    _collection_uri = 'variations'
    _collection_key = 'variations'
    _resource_class = Variation
