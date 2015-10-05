# -*- coding: utf-8 -*-
"""
Utilities for Manwë unit tests.
"""


import os
import re
import shutil
import tempfile

import httpretty
import varda
import varda.api
import varda.models

from manwe import Session
from manwe.config import Config


class TestEnvironment(object):
    """
    Test class providing an isolated test environment with API calls mocked
    and proxied to a temporary in-memory Varda API.
    """
    api_root = 'http://varda.test/'

    def setup(self):
        self._temp_dir = tempfile.mkdtemp(prefix='manwe-tests-')
        self._varda = varda.create_app({
            'TESTING': True,
            'DATA_DIR': self._temp_dir,
            'SECONDARY_DATA_DIR': os.path.dirname(os.path.realpath(__file__)),
            'GENOME': None,
            'REFERENCE_MISMATCH_ABORT': False,
            'SQLALCHEMY_DATABASE_URI': 'sqlite://',
            'BROKER_URL': 'memory://',
            'CELERY_RESULT_BACKEND': 'cache',
            'CELERY_CACHE_BACKEND': 'memory'
        })
        self._varda_app_context = self._varda.app_context()
        self._varda_app_context.push()

        varda.db.create_all()

        self._varda_client = self._varda.test_client()

        httpretty.enable()

        for method in (httpretty.GET, httpretty.POST, httpretty.PATCH,
                       httpretty.DELETE, httpretty.HEAD):
            httpretty.register_uri(method, re.compile('%s.*' % self.api_root),
                                   body=self._proxy_request)

        self.create_fixtures()

    def teardown(self):
        httpretty.disable()
        httpretty.reset()

        varda.db.session.remove()
        varda.db.drop_all()
        self._varda_app_context.pop()

        shutil.rmtree(self._temp_dir)

    def _proxy_request(self, request, uri, response_headers):
        """
        Proxy our HTTP request to the Varda API test client.
        """
        request_headers = dict(request.headers)
        content_type = request_headers.pop('content-type', None)
        request_headers.pop('content-length', None)
        data = request.body or None

        response = self._varda_client.open(
            uri, method=request.method, data=data, content_type=content_type,
            headers=request_headers)

        response_headers.update(response.headers)

        return response.status_code, response_headers, response.data

    def create_fixtures(self):
        """
        By default just create an admin account and a Manwë session for it.
        """
        admin = varda.models.User('Administrator', 'admin', 'testpassword',
                                  roles=['admin'])
        varda.db.session.add(admin)

        admin_token = varda.models.Token(admin, 'Test token')
        varda.db.session.add(admin_token)

        varda.db.session.commit()

        manwe_config = Config()
        manwe_config.update({
            'API_ROOT':        self.api_root,
            'TOKEN':           admin_token.key,
            'TASK_POLL_WAIT':  0.01
        })
        self.session = Session(config=manwe_config)

    def _uri_for_instance(self, resource, instance):
        with self._varda.test_request_context():
            return resource.instance_uri(instance)

    def _uri_for(self, model, resource, **criteria):
        instance = model.query.filter_by(**criteria).first()
        return self._uri_for_instance(resource, instance)

    def uri_for_annotation(self, **criteria):
        """
        Get API URI for an annotation.
        """
        return self._uri_for(varda.models.Annotation,
                             varda.api.views.annotations_resource, **criteria)

    def uri_for_data_source(self, **criteria):
        """
        Get API URI for a data source.
        """
        return self._uri_for(varda.models.DataSource,
                             varda.api.views.data_sources_resource, **criteria)

    def uri_for_group(self, **criteria):
        """
        Get API URI for a group.
        """
        return self._uri_for(varda.models.Group,
                             varda.api.views.groups_resource, **criteria)

    def uri_for_sample(self, **criteria):
        """
        Get API URI for a sample.
        """
        return self._uri_for(varda.models.Sample,
                             varda.api.views.samples_resource, **criteria)

    def uri_for_user(self, **criteria):
        """
        Get API URI for a user.
        """
        return self._uri_for(varda.models.User,
                             varda.api.views.users_resource, **criteria)
