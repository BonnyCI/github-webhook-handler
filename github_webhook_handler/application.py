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

import argparse
import os
import sys

import ipaddress
import requests
import webob
import webob.dec
import webob.exc
import yaml

from github_webhook_handler import handler

GITHUB_META_URL = 'https://api.github.com/meta'


class Request(webob.Request):

    _event_data = None

    @property
    def event_type(self):
        return self.headers.get('X-Github-Event')

    @property
    def event_data(self):
        """Cache the JSON body so as not to interpret it multiple times."""
        if self._event_data is None:
            self._event_data = self.json_body

        return self._event_data

    @property
    def signature(self):
        return self.headers.get('X-Hub-Signature')


def application(request, config):
    if request.path != '/':
        raise webob.exc.HTTPNotFound()

    if request.method != 'POST':
        raise webob.exc.HTTPMethodNotAllowed()

    request_ip = ipaddress.ip_address(request.client_addr.decode('utf-8'))
    hook_blocks = requests.get(GITHUB_META_URL).json()['hooks']

    for block in hook_blocks:
        if request_ip in ipaddress.ip_network(block):
            break
    else:
        raise webob.exc.HTTPForbidden()

    return handler.handle(config, request)


def initialize_application(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        dest='config',
                        default=os.environ.get('GWH_CONFIG_FILE'),
                        help='Config file to load')

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    config = {}

    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f) or {}

    return webob.dec.wsgify(application, args=(config,), RequestClass=Request)
