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

import contextlib
import shutil
import tempfile


def as_list(value):
    """Fetch a value that is either a single entry or a list as a list"""
    if not value:
        return []

    if not isinstance(value, list):
        value = [value]

    return value


def get_dotted_key(dictionary, key_str, default=None):
    """Fetch a value from a nested dictionary with keys of the form a.b.c"""
    key_list = key_str.split('.')
    key_val = key_list.pop()

    for key in key_list:
        try:
            dictionary = dictionary[key]
        except (KeyError, ValueError):
            return default

    return dictionary.get(key_val, default)


@contextlib.contextmanager
def mkdtemp(*args, **kwargs):
    """Create and then cleanup a temporary directory."""
    dirname = tempfile.mkdtemp(*args, **kwargs)

    try:
        yield dirname
    finally:
        shutil.rmtree(dirname)
