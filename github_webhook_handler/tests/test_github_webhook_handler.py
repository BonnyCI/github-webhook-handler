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

from github_webhook_handler.tests import base


class TestGithubWebhookHandler(base.TestCase):

    def test_non_root_gives_404(self):
        app = self.create_app()

        app.post('/abc', status=404)
        app.post('/def', status=404)
        app.post('/ghi/jkl', status=404)

    def test_not_post_gives_405(self):
        app = self.create_app()

        app.get('/', status=405)
        app.put('/', status=405)
        app.head('/', status=405)
