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
            self._dirty = set()
        # Todo: On save, refresh all fields from server.


class Sample(Resource):
    """
    Represents a sample.
    """
    _mutable = ('name', 'pool_size', 'coverage_profile', 'public')
    _immutable = ('uri', 'user_uri', 'added')

    @property
    def added(self):
        added = self._fields.get('added')
        if not added:
            return None
        return dateutil.parser.parse(added)


class User(Resource):
    """
    Represents a user.
    """
    _mutable = ('login', 'password', 'name', 'roles')
    _immutable = ('uri', 'added')


class SampleCollection(object):
    """
    Base class for representing server resource collections, iterators
    returning :class:`Resource` instances.
    """
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
        response = self.session.get(self.session.uris['samples'],
                                    headers={'Range': range})
        self._resources.extend(Sample(self.session, sample)
                               for sample in response.json()['samples'])
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
