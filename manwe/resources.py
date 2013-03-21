# -*- coding: utf-8 -*-
"""
Manwë resources.
"""


import collections

import dateutil.parser
import werkzeug.http

from .errors import NotFoundError


COLLECTION_CACHE_SIZE = 20


class Resource(object):
    """
    Base class for representing server resources.
    """
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
                # Todo: This won't work for structured values such as lists
                #     or dictionaries (user.roles), since they can be modified
                #     without touching the setter method.
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
        return super(Resource, cls).__new__(cls, *args, **kwargs)

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


class ResourceCollection(object):
    """
    Base class for representing server resource collections, iterators
    returning :class:`Resource` instances.
    """
    # Index in `Session.uris` for the URI to this collection.
    _collection_uri = None

    # Key in API collection response objects to the list of resources.
    _collection_key = None

    # Resource class to use for instantiating resources in this collection.
    _resource_class = None

    def __init__(self, session):
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

        self._next = 0
        self._resources = collections.deque()
        self._get_resources()

    def __iter__(self):
        return self

    def _get_resources(self):
        if self._next is None:
            return
        # Todo: Use Range object from Werkzeug to construct this header.
        range = 'items=%d-%d' % (self._next,
                                 self._next + COLLECTION_CACHE_SIZE - 1)
        response = self.session.get(self.session.uris[self._collection_uri],
                                    headers={'Range': range})
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
        Return the next :class:`Resource` in the collection.
        """
        if not self._resources:
            self._get_resources()
        try:
            return self._resources.popleft()
        except IndexError:
            raise StopIteration()

    # Python 3 compatibility.
    __next__ = next


class Annotation(Resource):
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


class Coverage(Resource):
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


class DataSource(Resource):
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


class Sample(Resource):
    """
    Base class for representing a sample resource.
    """
    _mutable = ('name', 'pool_size', 'coverage_profile', 'public')
    _immutable = ('uri', 'user_uri', 'added')

    @property
    def added(self):
        return dateutil.parser.parse(self._fields['added'])

    @property
    def user(self):
        return self.session.user(self.user_uri)


class User(Resource):
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


class Variant(Resource):
    """
    Base class for representing a variant resource.
    """
    _immutable = ('uri', 'chromosome', 'position', 'reference', 'observed',
                  'global_frequency', 'sample_frequency')


class Variation(Resource):
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


class AnnotationCollection(ResourceCollection):
    """
    Class for representing an annotation resource collection as an iterator
    returning :class:`Annotation` instances.
    """
    _collection_uri = 'annotations'
    _collection_key = 'annotations'
    _resource_class = Annotation


class CoverageCollection(ResourceCollection):
    """
    Class for representing a coverage resource collection as an iterator
    returning :class:`Coverage` instances.
    """
    _collection_uri = 'coverages'
    _collection_key = 'coverages'
    _resource_class = Coverage


class DataSourceCollection(ResourceCollection):
    """
    Class for representing a data source resource collection as an iterator
    returning :class:`DataSource` instances.
    """
    _collection_uri = 'data_sources'
    _collection_key = 'data_sources'
    _resource_class = DataSource


class SampleCollection(ResourceCollection):
    """
    Class for representing a sample resource collection as an iterator
    returning :class:`Sample` instances.
    """
    _collection_uri = 'samples'
    _collection_key = 'samples'
    _resource_class = Sample


class UserCollection(ResourceCollection):
    """
    Class for representing a user resource collection as an iterator returning
    :class:`User` instances.
    """
    _collection_uri = 'users'
    _collection_key = 'users'
    _resource_class = User


class VariantCollection(ResourceCollection):
    """
    Class for representing a variant resource collection as an iterator
    returning :class:`Variant` instances.
    """
    _collection_uri = 'variants'
    _collection_key = 'variants'
    _resource_class = Variant


class VariationCollection(ResourceCollection):
    """
    Class for representing a variation resource collection as an iterator
    returning :class:`Variation` instances.
    """
    _collection_uri = 'variations'
    _collection_key = 'variations'
    _resource_class = Variation
