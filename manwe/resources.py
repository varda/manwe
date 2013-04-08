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

# This is in bytes. Should it be much higher?
DATA_BUFFER_SIZE = 1024


class classproperty(object):
    """
    Decorator for defining computed class attributes, dual to the `property`
    built-in complementary to the `classmethod` built-in.

    Example usage::

        >>> class Foo(object):
        ...     x= 4
        ...     @classproperty
        ...     def number(cls):
        ...         return cls.x
        ...
        >>> Foo().number
        4
        >>> Foo.number
        4

    Copied from `bobince <http://stackoverflow.com/a/3203659>`_.
    """
    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter(owner)


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
    # Todo: Use embedded resources to avoid many separate requests.

    # Key for this resource type is used in API response objects as index for
    # the resource definition and with the ``_collection`` suffix as index in
    # `Session.uris` for the URI to this resources' collection which is the
    # endpoint for listing and creating resources.
    # We can build all this on a single value in `key` because the server API
    # is consistent in using conventions for naming things.
    #: Key for this resource type.
    key = None

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
        Create a representation for a server resource from a dictionary.

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

    @classmethod
    def create(cls, session, data=None, files=None):
        """
        Create a new resource on the server and return a representation for
        it.
        """
        kwargs = {'data': data}
        if files:
            kwargs.update(files=files)
        response = session.post(session.uris[cls.key + '_collection'],
                                **kwargs)
        return getattr(session, cls.key)(response.headers['Location'])

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
    #: Resource class to use for instantiating resources in this collection.
    resource_class = None

    # Names by which the collection can be parameterized.
    _accepted_args = ()

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

        self._args = {arg: kwargs.get(arg) for arg in self._accepted_args}
        self._next = 0
        self._resources = collections.deque()
        self._get_resources()

    @classproperty
    def key(cls):
        """
        Key for this resource type.
        """
        return cls.resource_class.key

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
        range_ = werkzeug.datastructures.Range(
            'items', [(self._next, self._next + COLLECTION_CACHE_SIZE)])
        try:
            response = self.session.get(
                uri=self.session.uris[self.key + '_collection'],
                data=self._args,
                headers={'Range': range_.to_header()})
        except UnsatisfiableRangeError:
            # Todo: If we'd store the response object in the error object, we
            #     could check for the Content-Range header and if it's present
            #     use it to set `self.size`.
            self.size = 0
            self._next = None
            return
        self._resources.extend(
            self.resource_class(self.session, resource)
            for resource in response.json()['collection']['items'])
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
    Class for representing an annotation resource.
    """
    key = 'annotation'
    _immutable = ('uri', 'original_data_source', 'annotated_data_source')

    @classmethod
    def create(cls, session, data_source, global_frequency=True,
               sample_frequency=None):
        """
        Create a new annotation and return a representation for it.
        """
        sample_frequency = sample_frequency or []
        data = {'data_source': data_source,
                'global_frequency': global_frequency,
                'sample_frequency': sample_frequency}
        return super(Annotation, cls).create(session, data=data)

    @property
    def original_data_source(self):
        return self.session.data_source(
            self._fields['original_data_source']['uri'])

    @property
    def annotated_data_source(self):
        return self.session.data_source(
            self._fields['annotated_data_source']['uri'])


class AnnotationCollection(_ResourceCollection):
    """
    Class for representing an annotation resource collection as an iterator
    returning :class:`Annotation` instances.
    """
    resource_class = Annotation


class Coverage(_Resource):
    """
    Class for representing a coverage resource.
    """
    key = 'coverage'
    _immutable = ('uri', 'sample', 'data_source')

    @classmethod
    def create(cls, session, sample, data_source):
        """
        Create a new coverage and return a representation for it.
        """
        data = {'sample': sample,
                'data_source': data_source}
        return super(Coverage, cls).create(session, data=data)

    @property
    def sample(self):
        return self.session.sample(self._fields['sample']['uri'])

    @property
    def data_source(self):
        return self.session.data_source(self._fields['data_source']['uri'])


class CoverageCollection(_ResourceCollection):
    """
    Class for representing a coverage resource collection as an iterator
    returning :class:`Coverage` instances.
    """
    resource_class = Coverage
    _accepted_args = ('sample',)


class DataSource(_Resource):
    """
    Class for representing a data source resource.
    """
    key = 'data_source'
    _mutable = ('name',)
    _immutable = ('uri', 'user', 'data', 'name', 'filetype', 'gzipped',
                  'added')

    @classmethod
    def create(cls, session, name, filetype, gzipped=False, data=None,
               local_file=None):
        """
        Create a new data source and return a representation for it.
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
        return super(DataSource, cls).create(session, data=post_data,
                                             files=files)

    @property
    def added(self):
        return dateutil.parser.parse(self._fields['added'])

    @property
    def user(self):
        return self.session.user(self._fields['user']['uri'])

    @property
    def data(self):
        """
        Iterator over the data source data by chunks.
        """
        return self.session.get(self._fields['data']['uri'],
                                stream=True).iter_content(
            chunk_size=DATA_BUFFER_SIZE)


class DataSourceCollection(_ResourceCollection):
    """
    Class for representing a data source resource collection as an iterator
    returning :class:`DataSource` instances.
    """
    resource_class = DataSource


class Sample(_Resource):
    """
    Class for representing a sample resource.
    """
    key = 'sample'
    _mutable = ('name', 'pool_size', 'coverage_profile', 'public', 'active',
                'notes')
    _immutable = ('uri', 'user', 'added')

    @classmethod
    def create(cls, session, name, pool_size=1, coverage_profile=True,
               public=False, notes=None):
        """
        Create a new sample and return a representation for it.
        """
        data = {'name': name,
                'pool_size': pool_size,
                'coverage_profile': coverage_profile,
                'public': public,
                'notes': notes}
        return super(Sample, cls).create(session, data=data)

    @property
    def added(self):
        return dateutil.parser.parse(self._fields['added'])

    @property
    def user(self):
        return self.session.user(self._fields['user']['uri'])


class SampleCollection(_ResourceCollection):
    """
    Class for representing a sample resource collection as an iterator
    returning :class:`Sample` instances.
    """
    resource_class = Sample
    _accepted_args = ('user',)


class User(_Resource):
    """
    Class for representing a user resource.
    """
    key = 'user'
    # Todo: Should password be an ordinary field (with initial None) value
    #     like it is now? Or should we modify it through some change_password
    #     method?
    _mutable = ('password', 'name', 'email', 'roles')
    _immutable = ('uri', 'login', 'added')

    @classmethod
    def create(cls, session, login, password, name=None, email=None,
               roles=None):
        """
        Create a new user and return a representation for it.
        """
        data = {'login': login,
                'password': password,
                'name': name or login,
                'email': email,
                'roles': roles or []}
        return super(User, cls).create(session, data=data)

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


class UserCollection(_ResourceCollection):
    """
    Class for representing a user resource collection as an iterator returning
    :class:`User` instances.
    """
    resource_class = User


class Variant(_Resource):
    """
    Class for representing a variant resource.
    """
    key = 'variant'
    # Todo: The API for this resource has been changed.
    _immutable = ('uri', 'chromosome', 'position', 'reference', 'observed',
                  'global_frequency', 'sample_frequency')

    @classmethod
    def create(cls, session, chromosome, position, reference='', observed=''):
        """
        Create a new variant and return a representation for it.
        """
        data = {'chromosome': chromosome,
                'position': position,
                'reference': reference,
                'observed': observed}
        return super(Variant, cls).create(session, data=data)


class VariantCollection(_ResourceCollection):
    """
    Class for representing a variant resource collection as an iterator
    returning :class:`Variant` instances.
    """
    resource_class = Variant


class Variation(_Resource):
    """
    Class for representing a variation resource.
    """
    key = 'variation'
    _immutable = ('uri', 'sample', 'data_source')

    @classmethod
    def create(cls, session, sample, data_source, skip_filtered=True,
               use_genotypes=True, prefer_genotype_likelihoods=False):
        """
        Create a new variation and return a representation for it.
        """
        data = {'sample': sample,
                'data_source': data_source,
                'skip_filtered': skip_filtered,
                'use_genotypes': use_genotypes,
                'prefer_genotype_likelihoods': prefer_genotype_likelihoods}
        return super(Variation, cls).create(session, data=data)

    @property
    def sample(self):
        return self.session.sample(self._fields['sample']['uri'])

    @property
    def data_source(self):
        return self.session.data_source(self._fields['data_source']['uri'])


class VariationCollection(_ResourceCollection):
    """
    Class for representing a variation resource collection as an iterator
    returning :class:`Variation` instances.
    """
    resource_class = Variation
    _accepted_args = ('sample',)
