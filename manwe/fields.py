# -*- coding: utf-8 -*-
"""
Manwë resource fields.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import dateutil.parser


class Field(object):
    """
    Base class for resource field definitions.

    A field definition can convert field values from their API representation
    to their Python representation, and vice versa.
    """
    def __init__(self, key=None, mutable=False, hidden=False, default=None,
                 doc=None):
        """
        Create a field instance.

        :arg str key: Key by which this field is stored in the API.
        :arg bool mutable: If `True`, field values can be modified.
        :arg bool hidden: If `True`, field should not be shown.
        :arg default: Default field value (as a Python value).
        :arg str doc: Documentation string
        """
        #: Key by which this field is stored in the API. By default inherited
        #: from :attr:`name`.
        self.key = key

        #: If `True`, field values can be modified.
        self.mutable = mutable

        #: If `True`, field should not be shown.
        self.hidden = hidden

        #: Default field value (as an API value).
        self.default = self.from_python(default)

        #: Documentation string.
        self.doc = doc

        self._name = None

    @property
    def name(self):
        """
        Name by which this field is available on the resource class.
        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        if self.key is None:
            self.key = self.name

    def to_python(self, value, session=None):
        """
        Convert API value to Python value.

        This gets called from field getters, so the user gets a nice Python
        value when accessing the field.

        Subclasses for structured data (such as lists and dicts) should be
        careful to not return mutable structures here, since that would allow
        to bypass the field setter. For example, calling `field.append(v)`
        will not add `field` to the set of dirty fields and will not go
        through :meth:`from_python`. Actually, it might not even modify the
        API value on the resource, because :meth:`to_python` probably created
        a copy.

        One solution for this, as implemented on :class:`Set`, is to return an
        immutable field value (a `frozenset` in this case) and thereby force
        modifications through the field setter.

        Another approach would be something similar to the `MutableDict` type
        in SQLAlchemy (see `Mutation Tracking
        <http://docs.sqlalchemy.org/en/latest/orm/extensions/mutable.html>`_).

        This does not apply to :class:`Link` fields, where the value is itself
        a resource which should be modified using its own
        :meth:`resources.Resource.save` method.
        """
        return value

    def from_python(self, value):
        """
        Convert Python value to API value.
        """
        return value


class Boolean(Field):
    pass


class Integer(Field):
    pass


class String(Field):
    pass


class Link(Field):
    """
    Definition for a resource link.
    """
    def __init__(self, resource_key, *args, **kwargs):
        """
        :arg str resource_key: Key for the linked resource.
        """
        self.resource_key = resource_key
        super(Link, self).__init__(*args, **kwargs)

    def to_python(self, value, session):
        """
        Create a :class:`resources.Resource` instance from the resource URI.

        Modifications of the returned resource should be saved by calling
        :meth:`resources.Resource.save` on that resource.
        """
        if value is None:
            return None
        # This is a bit ugly. In request data, a resource link is represented
        # by its uri (a string). But in response data, it is represented by an
        # object with a uri key.
        if isinstance(value, dict):
            uri = value['uri']
        else:
            uri = value
        return getattr(session, self.resource_key)(uri)

    def from_python(self, value):
        """
        In request data, a resource link is represented by its URI (a string).
        """
        if value is None:
            return None
        return value.uri


class DateTime(Field):
    def to_python(self, value, session=None):
        if value is None:
            return None
        return dateutil.parser.parse(value)

    def from_python(self, value):
        if value is None:
            return None
        return value.isoformat()


class Blob(Field):
    def to_python(self, value, session):
        """
        Iterator over the data source data by chunks.
        """
        if value is None:
            return None
        return session.get(value['uri'], stream=True).iter_content(
            chunk_size=session.config.DATA_BUFFER_SIZE)

    def from_python(self, value):
        if value is None:
            return None
        raise NotImplementedError()


class Set(Field):
    def __init__(self, field, *args, **kwargs):
        """
        :arg field: Field definition for the set members.
        :type field: :class:`Field`
        """
        self.field = field
        super(Set, self).__init__(*args, **kwargs)

    def to_python(self, value, session=None):
        """
        Convert the set to an immutable `fronzenset`. See the
        :meth:`Field.to_python` docstring.
        """
        if value is None:
            return None
        return frozenset(self.field.to_python(x, session) for x in value)

    def from_python(self, value):
        if value is None:
            return None
        return [self.field.from_python(x) for x in value]


class Task(Field):
    # TODO: Do something more intelligent.
    pass


class Queries(Field):
    """
    Definition for a field containing annotation queries.

    In the API, annotation queries are lists of dictionaries with `name` and
    `expression` items.

    As a Python value, we represent this as a dictionary with keys the query
    names and values the query expressions.
    """
    def to_python(self, value, session=None):
        if value is None:
            return None
        return {q['name']: q['expression'] for q in value}

    def from_python(self, value):
        if value is None:
            return None
        return [{'name': k, 'expression': v} for k, v in value.items()]
