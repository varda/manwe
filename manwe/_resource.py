"""
Manwë resources.
"""


class Resource(object):
    """
    Base class for representing server resources.
    """
    _mutable = ()
    _immutable = ()

    def __new__(cls, *args, **kwargs):
        def getter(name):
            def f(self):
                return self._fields.get(name)
            return f
        def setter(name):
            def f(self, value):
                self._dirty.add(name)
                self._fields[name] = value
            return f
        for name in cls._mutable:
            setattr(cls, name, property(getter(name), setter(name)))
        for name in cls._immutable:
            setattr(cls, name, property(getter(name)))
        return super(Resource, cls).__new__(cls, *args, **kwargs)

    def __init__(self, session, **fields):
        self.session = session
        self._dirty = set()
        self._fields = fields

    @property
    def dirty(self):
        return bool(self._dirty)

    def save(self):
        # Todo: On save, refresh all fields from server.
        self.session.request(self._fields['uri'], method='PATCH',
                             data={k: self._fields[k] for k in self._dirty})
        self._dirty = set()


class Sample(Resource):
    _mutable = ('name', 'pool_size', 'coverage_profile', 'public')
    _immutable = ('uri', 'user_uri', 'added')


class User(Resource):
    _mutable = ('login', 'password', 'name', 'roles')
    _immutable = ('uri', 'added')
