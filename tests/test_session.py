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
        mock_response = Mock(requests.Response, status_code=200)
        mock_response.json.return_value = collections.defaultdict(str)

        s = session.Session(config='/dev/null')
        s._cached_uris = collections.defaultdict(str)

        with patch.object(requests, 'request') as mock_request:
            mock_request.return_value = mock_response
            s.add_sample('test sample', pool_size=5, public=True)
            mock_request.assert_any_call('POST',
                                         '',
                                         data=json.dumps({'name': 'test sample',
                                                          'pool_size': 5,
                                                          'coverage_profile': True,
                                                          'public': True}),
                                         headers={'content-type': 'application/json'},
                                         auth=(None, None))
