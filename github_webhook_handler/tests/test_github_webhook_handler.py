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

import fixtures
import uuid

from github_webhook_handler import application
from github_webhook_handler.tests import base

get_handler = 'github_webhook_handler.handler.get_handlers'


class TestGithubWebhookHandler(base.TestCase):

    def setUp(self):
        super(TestGithubWebhookHandler, self).setUp()

        self.handlers = []
        self.useFixture(fixtures.MockPatch(get_handler, new=self.get_handlers))
        self.fake_popen = self.useFixture(fixtures.FakePopen())

    def get_handlers(self, config):
        return self.handlers

    def test_non_root_gives_404(self):
        app = self.create_app(full_application=True)

        app.post('/abc', status=404)
        app.post('/def', status=404)
        app.post('/ghi/jkl', status=404)

    def test_not_post_gives_405(self):
        app = self.create_app(full_application=True)

        app.get('/', status=405)
        app.put('/', status=405)
        app.head('/', status=405)

    def test_from_github_ip(self):
        # Example of real meta response:
        #
        # {
        #   "verifiable_password_authentication": true,
        #   "github_services_sha": "749995b7a788ea5070c900866007c448e04afd8f",
        #   "hooks": [
        #     "192.30.252.0/22"
        #   ],
        #   "git": [
        #     "192.30.252.0/22"
        #   ],
        #   "pages": [
        #     "192.30.252.153/32",
        #     "192.30.252.154/32"
        #   ],
        #   "importer": [
        #     "54.158.161.132",
        #     "54.226.70.38",
        #     "54.87.5.173",
        #     "54.166.52.62"
        #   ]
        # }

        resp_json = {'hooks': ['192.30.252.0/22']}

        self.requests_mock.get(application.GITHUB_META_URL,
                               headers={'Content-Type': 'application/json'},
                               json=resp_json)

        app = self.create_app(full_application=True)

        app.post('/', extra_environ={'REMOTE_ADDR': '10.0.0.1'}, status=403)
        app.post('/', extra_environ={'REMOTE_ADDR': '192.168.0.5'}, status=403)
        app.post('/', extra_environ={'REMOTE_ADDR': '192.30.252.88'})

    def test_unhandled_event_type(self):
        app = self.create_app()
        event_type = uuid.uuid4().hex
        headers = {'X-Github-Event': event_type}

        text = app.post('/', headers=headers).text
        self.assertEqual('Unhandled event type: %s' % event_type, text)

    def test_ping_no_signature(self):
        self.handlers = [
            {'repo': self.REPO_NAME}
        ]

        self.ping()

    def test_ping_bad_signature(self):
        self.handlers = [
            {'repo': self.REPO_NAME,
             'key': uuid.uuid4().hex}
        ]

        self.ping(signature=uuid.uuid4().hex, status=403)

    def test_push_no_actions(self):
        self.handlers = [
            {'repo': self.REPO_NAME}
        ]

        self.push()

    def test_push_bad_signature(self):
        self.handlers = [
            {'repo': self.REPO_NAME,
             'key': uuid.uuid4().hex}
        ]

        self.push(signature=uuid.uuid4().hex, status=403)

    def test_push_simple(self):
        before = uuid.uuid4().hex
        after = uuid.uuid4().hex

        self.handlers = [
            {'repo': self.REPO_NAME,
             'actions': ['./run.sh job'],
             'clone': False}
        ]

        self.push(before=before, after=after)

        self.assertEqual(1, len(self.fake_popen.procs))

        args = self.fake_popen.procs[0]._args['args']
        env = self.fake_popen.procs[0]._args['env']

        self.assertEqual(['./run.sh', 'job'], args)

        self.assertEqual(before, env['GWH_BEFORE'])
        self.assertEqual(after, env['GWH_AFTER'])
        self.assertEqual(self.REF, env['GWH_REF'])
