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
import shutil
import subprocess
import tempfile

import git
import webob
import webob.exc
import yaml


def handle(config, request):
    event_type = request.headers.get('X-Github-Event')

    if event_type == 'ping':
        return handle_ping(config, request)

    if event_type == 'push':
        return handle_push(config, request)

    # it's probably valid but not something we care about. Return OK.
    return webob.Response(status=200,
                          content_type='text/plain',
                          text=u'Unhandled event type: %s' % event_type)


def handle_ping(config, request):
    full_name = request.json['repository']['full_name']

    for handler in get_handlers(config):
        if handler.get('repo') == full_name:
            validate_signature(config, request, handler)

    return webob.Response(status=200,
                          content_type='text/plain',
                          text=u'pong')


def handle_push(config, request):
    full_name = request.json['repository']['full_name']

    for handler in get_handlers(config):
        if handler.get('repo') == full_name:
            # TODO(jamielennox): Only run on some branches
            # branch = repo.get('branch', '^master$')
            validate_signature(config, request, handler)
            run_actions(config, request, handler)

    return webob.Response(status=200)


def get_handlers(config):
    handlers_file = config.get('handlers')

    if not handlers_file:
        raise webob.exc.HTTPOk(comment='No handlers file available. Exiting.')

    with open(handlers_file, 'r') as f:
        return yaml.safe_load(f)


def validate_signature(config, request, handler):
    signature = request.headers.get('X-Hub-Signature')
    key = handler.get('key')

    if key and not signature:
        raise webob.exc.HTTPForbidden()

    elif signature and not key:
        raise webob.exc.HTTPForbidden()

    elif key:
        digest, value = signature.split('=')

        if digest != 'sha1':
            raise webob.exc.HTTPForbidden()

        mac = hmac.new(key, msg=request.body, digestmod=hashlib.sha1)

        if not hmac.compare_digest(mac.hexdigest(), value):
            raise webob.exc.HTTPForbidden()


def run_actions(config, request, handler):
    actions = handler.get('actions', [])

    if not actions:
        return

    event = request.json

    try:
        name = event.get('repository', {})['full_name']
        url = event.get('repository', {})['clone_url']
        commit = event['after']
        refspec = event['ref']
    except KeyError:
        raise RuntimeError("Bad event payload")

    env = os.environ.copy()

    env['GWH_REF'] = refspec
    env['GWH_BEFORE'] = event.get('before')
    env['GWH_AFTER'] = event.get('after')
    env['GWH_PUSHER_NAME'] = event.get('pusher', {}).get('name')
    env['GWH_PUSHER_EMAIL'] = event.get('pusher', {}).get('email')

    # working dir is a temporary directory the scripts are executed from
    working_dir = tempfile.mkdtemp()

    try:
        if handler.get('clone', True):
            working_git_dir = os.path.join(working_dir, 'repo')

            cache_dir = config.get('cache_dir',
                                   os.path.expanduser('~/gwh-cache'))
            cache_git_dir = os.path.join(cache_dir, name + '.git')

            create_temp_repo(working_git_dir,
                             cache_git_dir,
                             url,
                             commit,
                             refspec=refspec)

        for action in actions:
            cmd = shlex.split(action)
            p = subprocess.Popen(cmd, cwd=working_dir, env=env)
            p.communicate()

    finally:
        shutil.rmtree(working_dir)


def create_temp_repo(working_dir, git_dir, url, commit, refspec=None):
    """Checkout a local working copy of a repository.

    Clone the URL in the github webhook into a cache directory, ensure that the
    latest commits are present and then clone that into a temporary directory
    that a script can modify.
    """
    cache_git_repo = git.Repo.init(git_dir, bare=True, mkdir=True)

    try:
        cache_git_repo.delete_remote('origin')
    except git.GitCommandError:
        pass

    origin = cache_git_repo.create_remote('origin', url)
    origin.fetch(refspec=refspec)

    working_git_repo = cache_git_repo.clone(working_dir)

    try:
        working_git_repo.head.reference = cache_git_repo.commit(commit)
    except git.BadName:
        # can't find the given commit
        raise

    try:
        working_git_repo.delete_remote('origin')
    except git.GitCommandError:
        pass

    working_git_repo.create_remote('origin', url)
    working_git_repo.head.reset(index=True, working_tree=True)
