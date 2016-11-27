# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import uuid

from requests_mock.contrib import fixture
import testtools
import webob.dec
import webtest

from github_webhook_handler import application
from github_webhook_handler import handler


def _flip_handler_args(request, config):
    return handler.handle(config, request)


class TestCase(testtools.TestCase):
    """Test case base class for all unit tests."""

    REPO_NAME = 'test/repo'
    CLONE_URL = 'https://github.com/bonnyci/github-webhook-handler'
    REF = 'refs/heads/master'

    def setUp(self):
        super(TestCase, self).setUp()
        self.requests_mock = self.useFixture(fixture.Fixture())

    def create_app(self, config=None, full_application=False):
        config = config or {}

        # application does some checks on routing and if the caller is coming
        # from a github IP address. We don't need that generally so we can set
        # full_application=False to jump straight to the handler.
        if full_application:
            app = application.application
        else:
            app = _flip_handler_args

        wsgi = webob.dec.wsgify(app,
                                args=(config,),
                                RequestClass=application.Request)

        return webtest.TestApp(wsgi)

    def post(self, data, **kwargs):
        app = self.create_app(
            config=kwargs.pop('config', {}),
            full_application=kwargs.pop('full_application', False))

        headers = kwargs.setdefault('headers', {})

        try:
            signature = kwargs.pop('signature')
        except KeyError:
            pass
        else:
            headers['X-Hub-Signature'] = 'sha1=%s' % signature

        return app.post_json('/', data, **kwargs)

    def ping(self, data=None, **kwargs):
        data = data or {}

        headers = kwargs.setdefault('headers', {})
        headers['X-Github-Event'] = 'ping'

        repository = data.setdefault('repository', {})
        repository.setdefault('full_name', self.REPO_NAME)

        return self.post(data, **kwargs)

    def push(self, data=None, **kwargs):
        data = data or {}

        headers = kwargs.setdefault('headers', {})
        headers['X-Github-Event'] = 'push'

        data.setdefault('before', kwargs.pop('before', uuid.uuid4().hex))
        data.setdefault('after', kwargs.pop('after', uuid.uuid4().hex))
        data.setdefault('ref', kwargs.pop('ref', self.REF))

        repository = data.setdefault('repository', {})
        repository.setdefault('full_name', self.REPO_NAME)
        repository.setdefault('clone_url', self.CLONE_URL)

        return self.post(data, **kwargs)
