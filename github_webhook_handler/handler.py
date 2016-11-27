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

import hashlib
import hmac
import os
import os.path
import shlex
import subprocess

import webob
import webob.exc
import yaml

from github_webhook_handler import utils


def handle(config, request):
    for handler in _handlers_from_file(config):
        if filter_handler(config, request, handler):
            validate_signature(config, request, handler)
            run_action(config, request, handler)

    return webob.Response(status=200,
                          content_type='application/json',
                          json={})


def _handlers_from_file(config):
    # seperate so it can be mocked out in testing
    handlers_file = config.get('handlers')

    if not handlers_file:
        raise webob.exc.HTTPOk(comment='No handlers file available. Exiting.')

    with open(handlers_file, 'r') as f:
        return yaml.safe_load(f)


def filter_handler(config, request, handler):
    full_name = request.event_data.get('repository', {}).get('full_name')

    if request.event_type not in utils.as_list(handler.get('type', ['push'])):
        return False

    if full_name not in utils.as_list(handler.get('repo')):
        return False

    for name, matcher in handler.get('filter', {}).items():
        filter_val = utils.get_dotted_key(request.event_data, name)

        if matcher not in utils.as_list(filter_val):
            return False

    return True


def validate_signature(config, request, handler):
    key = handler.get('key')

    if key and not request.signature:
        raise webob.exc.HTTPForbidden()

    elif request.signature and not key:
        raise webob.exc.HTTPForbidden()

    elif key:
        digest, value = request.signature.split('=')

        if digest != 'sha1':
            raise webob.exc.HTTPForbidden()

        mac = hmac.new(key, msg=request.body, digestmod=hashlib.sha1)

        if not hmac.compare_digest(mac.hexdigest(), value):
            raise webob.exc.HTTPForbidden()


def run_action(config, request, handler):
    action = handler.get('action')

    if not action:
        return

    env = os.environ.copy()
    env['GWH_EVENT_TYPE'] = request.event_type

    cache_dir = config.get('cache_dir')
    if cache_dir:
        env['GWH_CACHE_DIR'] = cache_dir

    # working dir is a temporary directory the scripts are executed from
    with utils.mkdtemp() as working_dir:
        event_file = os.path.join(working_dir, 'event.json')
        env['GWH_EVENT_FILE'] = event_file

        with open(event_file, 'w') as f:
            f.write(request.text)

        p = subprocess.Popen(shlex.split(action), cwd=working_dir, env=env)
        p.communicate()
