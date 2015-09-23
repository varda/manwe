# -*- coding: utf-8 -*-
"""
Manwë resources.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import collections

import werkzeug.datastructures
import werkzeug.http

from .errors import UnsatisfiableRangeError
from .fields import (Blob, Boolean, DateTime, Field, Integer, Link, Queries,
                     Set, String, Task)


# This mirrors `varda.models.USER_ROLES`.
USER_ROLES = (
    'admin',         # Can do anything.
    'importer',      # Can import samples.
    'annotator',     # Can annotate variants.
    'trader',        # Can annotate variants if they are in an active sample.
    'querier',       # Can use any query expression when annotating.
    'group-querier'  # Can use group query expressions when annotating.
)


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


class ResourceMeta(type):
    def __new__(cls, name, parents, attributes):
        """
        Create a new class with field getters and setters.

        Similar to `how Django model fields work
        <https://code.djangoproject.com/wiki/DevModelCreation>`, this sets up
        getters and setters on resource classes. The field values are stored
        in the `_values` instance attribute.
        """
        fields = set()

        # Inherit all fields from parent classes.
        fields.update(*[parent._fields for parent in parents
                        if isinstance(parent, ResourceMeta)])

        for name_, attribute in attributes.items():
            if not isinstance(attribute, Field):
                continue

            # Store the name under which the field is available on the class
            # in the field itself.
            attribute.name = name_
            fields.add(attribute)

            # Hidden field definitions are useful for resource creation
            # arguments which are not available in the resulting resource's
            # representation.
            if attribute.hidden:
                continue

            if attribute.mutable:
                attributes[name_] = property(cls._getter(attribute),
                                             cls._setter(attribute),
                                             doc=attribute.doc)
            else:
                attributes[name_] = property(cls._getter(attribute),
                                             doc=attribute.doc)

        attributes['_fields'] = fields

        return super(ResourceMeta, cls).__new__(cls, name, parents, attributes)

    @staticmethod
    def _getter(field):
        def getter_for_field(self):
            return field.to_python(self._values.get(field.name),
                                   self.session)
        return getter_for_field

    @staticmethod
    def _setter(field):
        def setter_for_field(self, value):
            # TODO: validation?
            self._dirty.add(field.name)
            self._values[field.name] = field.from_python(value)
        return setter_for_field


class Resource(object):
    """
    Base class for representing server resources.

    Resource fields are defined as class attributes by :mod:`Field` instances.
    """
    __metaclass__ = ResourceMeta

    # Todo: Use embedded resources to avoid many separate requests.

    # Key for this resource type is used in API response objects as index for
    # the resource definition and with the ``_collection`` suffix as index in
    # `Session.endpoints` for the URI to this resources' collection which is
    # the endpoint for listing and creating resources.
    # We can build all this on a single value in `key` because the server API
    # is consistent in using conventions for naming things.
    #: Key for this resource type.
    key = None

    #: Resource URI.
    uri = String()

    def __init__(self, session, values):
        """
        Create a representation for a server resource from a dictionary.

        :arg session: Manwë session.
        :type session: :class:`.Session`
        :arg values: Dictionary with field values (using API keys and values).
        :type values: dict
        """
        #: The session this resource is attached to as
        #: :class:`.Session <Session>`.
        self.session = session

        # Names of fields that are dirty.
        self._dirty = set()

        # Load field values from parsed response JSON.
        self._load_values(values)

    @classmethod
    def create(cls, session, values=None, files=None):
        """
        Create a new resource on the server and return a representation for
        it.

        :arg session: Manwë session.
        :type session: :class:`.Session`
        :arg values: Dictionary with field values (using Python names and
          values).
        :type values: dict
        :arg files: Open file objects.
        :type files: dict(str, file-like object)

        Every subclass should override this with an informative docstring.
        """
        values = values or {}

        data = {field.key: field.from_python(values[field.name])
                for field in cls._fields
                if field.name in values}

        kwargs = {'data': data}
        if files:
            kwargs.update(files=files)

        response = session.post(session.endpoints[cls.key + '_collection'],
                                **kwargs)
        return getattr(session, cls.key)(response.headers['Location'])

    def _load_values(self, values):
        # API values, not Python values.
        self._values = {field.name: values[field.key]
                        if field.key in values else field.default
                        for field in self._fields}
        self._dirty.clear()

    def __repr__(self):
        if self._values:
            values = ' ' + ' '.join('%s=%r' % x for x in self._values.items())
        else:
            values = ''
        return '<%s%s>' % (self.__class__.__name__, values)

    def __str__(self):
        return self.uri

    def __hash__(self):
        return hash(self.uri)

    def __eq__(self, other):
        return self.uri and other.uri and self.uri == other.uri

    @property
    def dirty(self):
        """
        `True` if there are any unsaved changes on this resource, `False`
        otherwise.
        """
        return bool(self._dirty)

    def refresh(self):
        """
        Refresh field values from server.
        """
        response = self.session.get(self.uri)
        self._load_values(response.json()[self.key])

    def save(self):
        """
        Save any unsaved changes on this resource.
        """
        if self.dirty:
            self.session.patch(self.uri,
                               data={field.key: getattr(self, field.name)
                                     for field in self._fields
                                     if field.name in self._dirty})
            self._dirty.clear()


class TaskedResource(Resource):
    """
    Base class for representing server resources with tasks.
    """
    # Todo: Implement task specific functionality.
    task = Task()


class ResourceCollection(object):
    """
    Base class for representing server resource collections, iterators
    returning :class:`Resource` instances.

    Collection filters are defined as class attributes by :mod:`Field`
    instances (and must not be mutable).
    """
    __metaclass__ = ResourceMeta

    #: Resource class to use for instantiating resources in this collection.
    resource_class = None

    def __init__(self, session, values=None):
        """
        Create a representation for a server resource collection.

        :arg session: Manwë session.
        :type session: :class:`.Session`
        :arg values: Dictionary with field values (using Python names and
          values).
        :type values: dict

        Every subclass should override this with an informative docstring.
        """
        values = values or {}

        #: The session this resource collection  is attached to as
        #: :class:`.Session <Session>`.
        self.session = session

        #: The total number of resources in this collection as last reported
        #: by the server. Note that the actual number of resources produced by
        #: the collection iterator might deviate from this number, and this is
        #: why there is not `__len__` property defined.
        self.size = 0

        # API values, not Python values.
        self._values = {field.name: field.from_python(values[field.name])
                        if field.name in values else field.default
                        for field in self._fields}

        # This is not used.
        self._dirty = set()

        # Cached collection of resources.
        self._resources = collections.deque()

        # Start from the beginning.
        self.reset()

    @classproperty
    def key(cls):
        """
        Key for this resource type.
        """
        return cls.resource_class.key

    def reset(self):
        """
        Reset resource collection iterator.
        """
        self._next = 0
        self._resources.clear()
        self._get_resources()

    def __repr__(self):
        if self._values:
            values = ' ' + ' '.join('%s=%r' % x for x in self._values.items())
        else:
            values = ''
        return '<%s%s>' % (self.__class__.__name__, values)

    def __iter__(self):
        return self

    @property
    def cache_size(self):
        """
        Number of resources to query per collection request.
        """
        return self.session.config.COLLECTION_CACHE_SIZE

    def _get_resources(self):
        if self._next is None:
            return
        range_ = werkzeug.datastructures.Range(
            'items', [(self._next, self._next + self.cache_size)])
        try:
            response = self.session.get(
                uri=self.session.endpoints[self.key + '_collection'],
                data={field: value for field, value in self._values.items()
                      if value is not None},
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
            for resource in response.json()[self.key + '_collection']['items'])
        content_range = werkzeug.http.parse_content_range_header(
            response.headers['Content-Range'])
        self.size = content_range.length
        if content_range.stop < content_range.length:
            self._next += self.cache_size
        else:
            self._next = None

    def next(self):
        """
        Return the next resource in the collection.
        """
        if not self._resources:
            self._get_resources()
        try:
            return self._resources.popleft()
        except IndexError:
            raise StopIteration()

    # Python 3 compatibility.
    __next__ = next


class Annotation(TaskedResource):
    """
    Class for representing an annotation resource.
    """
    key = 'annotation'

    original_data_source = Link(
        'data_source',
        doc='Original data source (:class:`DataSource` instance).')
    annotated_data_source = Link(
        'data_source',
        doc='Annotated data source (:class:`DataSource` instance).')

    # These hidden fields define arguments for create() which are not in the
    # resulting resource's representation.
    data_source = Link('data_source', hidden=True)
    name = String(hidden=True)
    queries = Queries(hidden=True)

    @classmethod
    def create(cls, session, data_source, name=None, queries=None):
        """
        Create an annotation resource.

        :arg data_source: Data source to annotate.
        :type data_source: :class:`.DataSource`
        :arg name: Human readable annotation name.
        :type name: str
        :arg queries: Sample queries to calculate variant frequencies over.
          Keys are query identifiers (alphanumeric) and values are query
          expressions.
        :type queries: dict(str, str)

        :return: An annotation resource.
        :rtype: :class:`.Annotation`
        """
        queries = queries or {}

        values = {'data_source': data_source,
                  'queries': queries}
        if name is not None:
            values.update(name=name)
        return super(Annotation, cls).create(session, values=values)


class AnnotationCollection(ResourceCollection):
    """
    Class for representing an annotation resource collection as an iterator
    returning :class:`Annotation` instances.
    """
    resource_class = Annotation

    def __init__(self, session):
        """
        Query an annotation resource collection.

        :return: An annotation resource collection.
        :rtype: :class:`.AnnotationCollection`
        """
        super(AnnotationCollection, self).__init__(session)


class Coverage(TaskedResource):
    """
    Class for representing a coverage resource.
    """
    key = 'coverage'

    sample = Link('sample',
                  doc='Coverage is part of this :class:`Sample`.')
    data_source = Link('data_source',
                       doc='Coverage data (:class:`DataSource` instance).')

    @classmethod
    def create(cls, session, sample, data_source):
        """
        Create a coverage resource.

        :arg sample: Sample the coverage resource is part of.
        :type sample: :class:`.Sample`
        :arg data_source: Data source for the coverage resource.
        :type data_source: :class:`.DataSource`

        :return: A coverage resource.
        :rtype: :class:`.Coverage`
        """
        values = {'sample': sample,
                  'data_source': data_source}
        return super(Coverage, cls).create(session, values=values)


class CoverageCollection(ResourceCollection):
    """
    Class for representing a coverage resource collection as an iterator
    returning :class:`Coverage` instances.
    """
    resource_class = Coverage

    sample = Link('sample',
                  doc='Collection is filtered by this :class:`Sample`.')

    def __init__(self, session, sample=None):
        """
        Query a coverage resource collection.

        :arg sample: Filter collection by sample.
        :type sample: :class:`.Sample`

        :return: A coverage resource collection.
        :rtype: :class:`.CoverageCollection`
        """
        values = {'sample': sample}
        super(CoverageCollection, self).__init__(session, values=values)


class DataSource(Resource):
    """
    Class for representing a data source resource.
    """
    key = 'data_source'

    name = String(mutable=True, doc='Human readable data source name.')
    user = Link('user', doc='Data source is owned by this :class:`User`.')
    data = Blob(doc='Iterator yielding data as chunks.')
    filetype = String(doc='Data filetype.')  # TODO: field type?
    gzipped = Boolean(doc='If `True`, `data` is compressed using gzip.')
    added = DateTime(doc='Date and time this data source was added.')

    @classmethod
    def create(cls, session, name, filetype, gzipped=False, data=None,
               local_file=None):
        """
        Create a data source resource.

        :arg str name: Human readable data source name.
        :arg str filetype: Data filetype. Possible values are ``bed``, ``vcf``,
          and ``csv``.
        :arg bool gzipped: Whether or not the data is compressed using gzip.
        :arg data: Data blob.
        :type data: file-like object
        :arg str local_file: A filename on the server filesystem. This can be
          used instead of `data`.

        :return: A data source resource.
        :rtype: :class:`.DataSource`
        """
        values = {'name': name,
                  'filetype': filetype,
                  'gzipped': gzipped}
        if local_file:
            values.update(local_file=local_file)
        if data is None:
            files = None
        else:
            files = {'data': data}
        return super(DataSource, cls).create(session, values=values,
                                             files=files)


class DataSourceCollection(ResourceCollection):
    """
    Class for representing a data source resource collection as an iterator
    returning :class:`DataSource` instances.
    """
    resource_class = DataSource

    user = Link('user',
                doc='Collection is filtered by this :class:`User`.')

    def __init__(self, session, user=None):
        """
        Query a data source resource collection.

        :arg user: Filter collection by user.
        :type user: :class:`.User`

        :return: A data source resource collection.
        :rtype: :class:`.DataSourceCollection`
        """
        values = {'user': user}
        super(DataSourceCollection, self).__init__(session, values=values)


class Group(Resource):
    """
    Class for representing a group resource.
    """
    key = 'group'

    name = String(mutable=True, doc='Human readable group name.')

    @classmethod
    def create(cls, session, name):
        """
        Create a group resource.

        :arg str name: Human readable group name.

        :return: A group resource.
        :rtype: :class:`.Group`
        """
        values = {'name': name}
        return super(Group, cls).create(session, values=values)


class GroupCollection(ResourceCollection):
    """
    Class for representing a group resource collection as an iterator
    returning :class:`Group` instances.
    """
    resource_class = Group

    def __init__(self, session):
        """
        Query a group resource collection.

        :return: A group resource collection.
        :rtype: :class:`.GroupCollection`
        """
        super(GroupCollection, self).__init__(session)


class Sample(Resource):
    """
    Class for representing a sample resource.
    """
    key = 'sample'

    user = Link('user', doc='Sample is owned by this :class:`User`.')
    name = String(mutable=True, doc='Human readable sample name.')
    pool_size = Integer(mutable=True, doc='Number of individuals.')
    coverage_profile = Boolean(
        mutable=True, doc='If `True`, the sample has a coverage profile.')
    public = Boolean(mutable=True, doc='If `True`, the sample is public.')
    notes = String(mutable=True, doc='Human readable notes in Markdown format.')
    groups = Set(
        Link('group'), mutable=True,
        doc='Sample is part of these groups (:class:`Group` instances).')
    active = Boolean(mutable=True, doc='If `True`, the sample is active.')
    added = DateTime(doc='Date and time this sample was added.')

    @classmethod
    def create(cls, session, name, pool_size=1, coverage_profile=True,
               public=False, notes=None, groups=None):
        """
        Create a sample resource.

        :arg str name: Human readable sample name.
        :arg int pool_size: Number of individuals in the sample.
        :arg bool coverage_profile: Whether or not the sample has a coverage
          profile.
        :arg bool public: Whether or not this sample is public.
        :arg str notes: Human readable notes in Markdown format.
        :arg groups: Groups this sample is part of.
        :type groups: iterable(:class:`.DataSource`)

        :return: A sample resource.
        :rtype: :class:`.Sample`
        """
        groups = groups or []

        values = {'name': name,
                  'pool_size': pool_size,
                  'coverage_profile': coverage_profile,
                  'public': public,
                  'groups': groups}
        if notes is not None:
            values.update(notes=notes)
        return super(Sample, cls).create(session, values=values)


class SampleCollection(ResourceCollection):
    """
    Class for representing a sample resource collection as an iterator
    returning :class:`Sample` instances.
    """
    resource_class = Sample

    groups = Set(Link('group'), doc='Collection is filtered by these groups'
                 ' (:class:`Group` instances).')
    public = Boolean(doc='Collection is filtered by this public state.')
    user = Link('user',
                doc='Collection is filtered by this :class:`User`.')

    def __init__(self, session, groups=None, public=None, user=None):
        """
        Query a sample resource collection.

        :arg groups: Filter collection by groups.
        :type groups: iterable(:class:`.DataSource`)
        :arg public: Filter collection by public/non-public.
        :type public: bool
        :arg user: Filter collection by user.
        :type user: :class:`.User`

        :return: A sample resource collection.
        :rtype: :class:`.SampleCollection`
        """
        values = {'groups': groups,
                  'public': public,
                  'user': user}
        super(SampleCollection, self).__init__(session, values=values)


class User(Resource):
    """
    Class for representing a user resource.
    """
    key = 'user'

    # Todo: Should password be an ordinary field (with initial None) value
    #     like it is now? Or should we modify it through some change_password
    #     method?

    login = String(doc='Login name.')
    password = String(mutable=True, doc='Password used for authentication.')
    name = String(mutable=True, doc='Human readable user name.')
    email = String(mutable=True, doc='Email address.')
    roles = Set(String(), mutable=True, doc='Roles for this user.')
    added = DateTime(doc='Date and time this user was added.')

    @classmethod
    def create(cls, session, login, password, name=None, email=None,
               roles=None):
        """
        Create a user resource.

        :arg str login: Login name used for authentication.
        :arg str password: Password used for authentication.
        :arg str name: Human readable user name.
        :arg str email: User e-mail address.
        :arg roles: Roles for this user (values must be from
          :data:`.USER_ROLES`).
        :type roles: iterable(str)

        :return: A user resource.
        :rtype: :class:`.User`
        """
        roles = roles or []

        values = {'login': login,
                  'password': password,
                  'name': name or login,
                  'roles': roles}
        if email is not None:
            values.update(email=email)
        return super(User, cls).create(session, values=values)


class UserCollection(ResourceCollection):
    """
    Class for representing a user resource collection as an iterator returning
    :class:`User` instances.
    """
    resource_class = User

    def __init__(self, session):
        """
        Query a user resource collection.

        :return: A user resource collection.
        :rtype: :class:`.UserCollection`
        """
        super(UserCollection, self).__init__(session)


class Variant(Resource):
    """
    Class for representing a variant resource.
    """
    key = 'variant'

    chromosome = String(doc='Chromosome name.')
    position = Integer(doc='Position of variant on `chromosome`.')
    reference = String(doc='Reference allele.')
    observed = String(doc='Observed allele.')

    @classmethod
    def create(cls, session, chromosome, position, reference='', observed=''):
        """
        Create a variant resource.

        :arg str chromosome: Chromosome name.
        :arg int position: Position of variant on `chromosome`.
        :arg str reference: Reference allele.
        :arg str observed: Observed allele.

        :return: A variant resource.
        :rtype: :class:`.Variant`
        """
        values = {'chromosome': chromosome,
                  'position': position,
                  'reference': reference,
                  'observed': observed}
        return super(Variant, cls).create(session, values=values)

    def annotate(self, queries=None):
        """
        Annotate this variant with the observed frequencies over sets of
        samples

        :arg queries: Sample queries to calculate variant frequencies over.
          Keys are query identifiers (alphanumeric) and values are query
          expressions.
        :type queries: dict(str, str)

        :return: Variant observation frequencies. Keys are query identifiers
          and values are dictionaries with `coverage`, `frequency`,
          `frequency_het`, and `frequency_hom`.
        :rtype: dict(str, dict)
        """
        queries = queries or {}

        variant = self.session.get(
            uri=self.uri,
            data={'queries': [{'name': k, 'expression': v}
                              for k, v in queries.items()]}).json()['variant']
        return variant['annotations']


class VariantCollection(ResourceCollection):
    """
    Class for representing a variant resource collection as an iterator
    returning :class:`Variant` instances.
    """
    resource_class = Variant

    def __init__(self, session):
        """
        Query a variant resource collection.

        :return: A variant resource collection.
        :rtype: :class:`.VariantCollection`
        """
        super(VariantCollection, self).__init__(session)


class Variation(TaskedResource):
    """
    Class for representing a variation resource.
    """
    key = 'variation'

    sample = Link('sample',
                  doc='Variation is part of this :class:`Sample`.')
    data_source = Link('data_source',
                       doc='Variation data (:class:`DataSource` instance).')

    @classmethod
    def create(cls, session, sample, data_source, skip_filtered=True,
               use_genotypes=True, prefer_genotype_likelihoods=False):
        """
        Create a variation resource.

        :arg sample: Sample the variation resource is part of.
        :type sample: :class:`.Sample`
        :arg data_source: Data source for the variation resource.
        :type data_source: :class:`.DataSource`
        :arg bool skip_filtered: Discard entries in `data_source` marked as
          filtered.
        :arg bool use_genotypes: Use per-sample genotype information from
          `data_source`.
        :arg bool prefer_genotype_likelihoods: Prefer using genotype
          likelihoods from `data_source` instead of concrete genotypes.

        :return: A variation resource.
        :rtype: :class:`.Variation`
        """
        values = {'sample': sample,
                  'data_source': data_source,
                  'skip_filtered': skip_filtered,
                  'use_genotypes': use_genotypes,
                  'prefer_genotype_likelihoods': prefer_genotype_likelihoods}
        return super(Variation, cls).create(session, values=values)


class VariationCollection(ResourceCollection):
    """
    Class for representing a variation resource collection as an iterator
    returning :class:`Variation` instances.
    """
    resource_class = Variation

    sample = Link('sample',
                  doc='Collection is filtered by this :class:`Sample`.')

    def __init__(self, session, sample=None):
        """
        Query a variation resource collection.

        :arg sample: Filter collection by sample.
        :type sample: :class:`.Sample`

        :return: A variation resource collection.
        :rtype: :class:`.VariationCollection`
        """
        values = {'sample': sample}
        super(VariationCollection, self).__init__(session, values=values)
