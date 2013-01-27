"""
Manwe sessions.
"""


# Todo: Handle requests.exceptions.ConnectionError.


import json
import requests
from requests import codes

from .config import Config
from .resource import Sample, User


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
        data = data or {}
        auth = self.config.user, self.config.password
        response = requests.request(method, uri, data=data, auth=auth)
        print response.text
        return response

    def sample(self, uri):
        response = self.request(uri)
        return Sample.from_dict(response.json()['sample'])

    def user(self, uri):
        response = self.request(uri)
        return User.from_dict(response.json()['user'])

    def save(self, instance):
        if not instance.uri:
            response = self.request(self.uris[instance._collection], method='POST',
                                    data=instance._fields_all)
            instance._uri = response.headers['location']
        elif instance.dirty:
            self.request(instance.uri, method='PATCH',
                         data=instance._fields_dirty)
        instance._clean()
