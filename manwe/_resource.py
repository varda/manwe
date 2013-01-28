"""
Manwe resources.
"""


class Resource(object):
    """
    Base class for representing server resources.
    """
    _mutable = ()
    _immutable = ()

    def __new__(cls, *args, **kwargs):
        for name in cls._mutable:
            def getter(self):
                return self._fields.get(name)
            def setter(self, value):
                self._dirty.add(name)
                self._fields[name] = value
            cls.setattr(name, property(getter, setter))
        for name in cls._immutable:
            def getter(self):
                return self._fields.get(name)
            cls.setattr(name, property(getter))

    def __init__(self, **fields):
        super(Sample, self).__init__()
        self._dirty = set()
        self._fields = fields

    @property
    def dirty(self):
        return bool(self._dirty)


class Sample(Resource):
    _mutable = ('name', 'pool_size', 'coverage_profile', 'public')
    _immutable = ('uri', 'user_uri', 'added')


class User(Resource):
    _mutable = ('login', 'password', 'name', 'roles')
    _immutable = ('uri', 'added')
