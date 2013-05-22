"""
Unit tests for :mod:`manwe.session`.
"""


import collections

import json
from mock import Mock, patch
from nose.tools import *
import requests

from manwe import config, session


class TestSession():
    """
    Test :mod:`manwe.session`.
    """
    def test_add_sample(self):
        """
        Adding a sample causes the correct POST request to be sent to the
        server.
        """
        mock_response = Mock(requests.Response, status_code=200,
                             headers={'Location': '/'})
        mock_response.json.return_value = collections.defaultdict(str)

        s = session.Session(config='/dev/null')
        s._cached_uris = {'sample_collection': 'http://samples/'}

        with patch.object(requests, 'request') as mock_request:
            mock_request.return_value = mock_response
            s.add_sample('test sample', pool_size=5, public=True)
            mock_request.assert_any_call('POST', 'http://samples/',
                                         data=json.dumps({'name': 'test sample',
                                                          'pool_size': 5,
                                                          'coverage_profile': True,
                                                          'public': True}),
                                         headers={'Content-Type': 'application/json',
                                                  'Accept-Version': session.ACCEPT_VERSION})

    def test_add_data_source(self):
        """
        Adding a data source causes the correct POST request to be sent to the
        server.
        """
        mock_response = Mock(requests.Response, status_code=200,
                             headers={'Location': '/'})
        mock_response.json.return_value = collections.defaultdict(str)

        s = session.Session(config='/dev/null')
        s._cached_uris = {'data_source_collection': 'http://data_sources/'}

        test_data = 'test data'

        with patch.object(requests, 'request') as mock_request:
            mock_request.return_value = mock_response
            s.add_data_source('test data source', 'vcf', data=test_data)
            mock_request.assert_any_call('POST', 'http://data_sources/',
                                         data={'name': 'test data source',
                                               'filetype': 'vcf',
                                               'gzipped': False},
                                         files={'data': test_data},
                                         headers={'Accept-Version': session.ACCEPT_VERSION})
