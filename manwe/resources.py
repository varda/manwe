# -*- coding: utf-8 -*-
"""
Manwë resources.
"""


import collections

import dateutil.parser

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
    # Note that we don't implement __len__ on purpose, since we load the
    # resources a few at a time, lazily, and what's on the server could always
    # change under our nose.
    # We might however implement another property (e.g. `size`) that is set
    # using the Content-Range response header value and clearly document that
    # it might deviate from the actual number of items the iterator produces.
    def __init__(self, session):
        """
        Create a representation for a server resource collection.
        """
        #: The session this resource collection  is attached to as
        #: :class:`session.Session <Session>`.
        self.session = session
        self._next = 0
        self._resources = collections.deque()

    def __iter__(self):
        return self

    def _get_resources(self):
        if self._next is not None:
            range = 'items=%d-%d' % (self._next,
                                     self._next + COLLECTION_CACHE_SIZE - 1)
            try:
                response = self.session.get(self.session.uris['samples'],
                                            headers={'Range': range})
            except NotFoundError:
                # Todo: Instead of checking for 404 Not Found here, it would
                #     better to actually check the value of the Content-Range
                #     header in each request and act appropriately.
                self._next = None
            else:
                self._resources.extend(Sample(self.session, sample)
                                       for sample in response['samples'])
                self._next += COLLECTION_CACHE_SIZE

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
