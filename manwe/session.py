"""
Manwe sessions.
"""


# Todo: Handle requests.exceptions.ConnectionError.


import json
import requests
from requests import codes

from .config import Config
from ._resource import Sample, User


class Session(object):
    """
    Session for interfacing the server API.
    """
    def __init__(self, config=None):
        """
        Create a `Session`.

        :arg config: Configuration filename.
        :type config: str
        """
        self.config = Config(filename=config)
        self._cached_uris = None

    @property
    def uris(self):
        if not self._cached_uris:
            response = self.request(self.config.api_root).json()
            self._cached_uris = {key: response[key + '_uri'] for key in
                                 ('authentication', 'users', 'samples',
                                  'variations', 'coverages', 'data_sources',
                                  'annotations', 'variants')}
        return self._cached_uris

    def request(self, uri, data=None, method='GET'):
        if uri.startswith('/'):
            if self.config.api_root.endswith('/'):
                uri = self.config.api_root + uri[1:]
            else:
                uri = self.config.api_root + uri
        data = json.dumps(data or {})
        auth = self.config.user, self.config.password
        response = requests.request(method, uri, data=data, headers={'content-type': 'application/json'}, auth=auth)
        print response.text
        return response

    def get_sample(self, uri):
        response = self.request(uri)
        return Sample(self, **response.json()['sample'])

    def get_user(self, uri):
        response = self.request(uri)
        return User(self, **response.json()['user'])

    def add_sample(self, name, pool_size=1, coverage_profile=True, public=False):
        response = self.request(self.uris['samples'], method='POST',
                                data=dict(name=name, pool_size=pool_size, coverage_profile=coverage_profile, public=public))
        return self.get_sample(response.json()['sample_uri'])

    def add_user(self, login, password, name=None, roles=None):
        name = name or login
        roles = roles or []
        response = self.request(self.uris['users'], method='POST',
                                data=dict(login=login, password=password,
                                          name=name, roles=roles))
        return self.get_user(response.json()['user_uri'])

    def save(self, instance):
        if not instance.uri:
            response = self.request(self.uris[instance._collection], method='POST',
                                    data=instance._fields_all)
            instance._uri = response.headers['location']
        elif instance.dirty:
            self.request(instance.uri, method='PATCH',
                         data=instance._fields_dirty)
        instance._clean()
