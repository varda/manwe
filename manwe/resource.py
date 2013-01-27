"""
Manwe resources.
"""


class Resource(object):
    """
    Base class for representing server resources.
    """
    _collection = None
    _fields = ()

    def __init__(self):
        self._dirty = set()
        self._uri = None
        self._track = True

    def __setattr__(self, name, value):
        if name in self._fields and hasattr(self, '_track'):
            self._dirty.add(name)
        super(Resource, self).__setattr__(name, value)

    @property
    def dirty(self):
        return bool(self._dirty)

    @property
    def uri(self):
        return self._uri

    @property
    def _fields_all(self):
        return {name: getattr(self, name) for name in self._fields}

    @property
    def _fields_dirty(self):
        return {name: getattr(self, name) for name in self._dirty}

    def _clean(self):
        self._dirty = set()

    @classmethod
    def from_dict(cls, dictionary):
        uri = dictionary.pop('uri')
        instance = cls(**dictionary)
        instance._uri = uri
        return instance


class Sample(Resource):
    _collection = 'samples'
    _fields = ('name', 'pool_size', 'coverage_profile', 'public')

    def __init__(self, name, pool_size=1, coverage_profile=True, public=False):
        self.name = name
        self.pool_size = pool_size
        self.coverage_profile = coverage_profile
        self.public = public
        self._added = None
        self._user_uri = None
        super(Sample, self).__init__()

    @property
    def added(self):
        return self._added

    @property
    def user_uri(self):
        return self._user_uri

    @classmethod
    def from_dict(cls, dictionary):
        added = dictionary.pop('added')
        user_uri = dictionary.pop('user_uri')
        instance = super(Sample, cls).from_dict(dictionary)
        instance._added = added
        instance._user_uri = user_uri
        return instance


class User(Resource):
    _collection = 'users'
    _fields = ('login', 'password', 'name', 'roles')

    def __init__(self, login, password, name=None, roles=None):
        self.login = login
        self.password = password
        self.name = name or login
        self.roles = set(roles or [])
        self._added = None
        super(User, self).__init__()

    @property
    def added(self):
        return self._added

    @classmethod
    def from_dict(cls, dictionary):
        dictionary['password'] = None
        added = dictionary.pop('added')
        instance = super(User, cls).from_dict(dictionary)
        instance._added = added
        return instance
