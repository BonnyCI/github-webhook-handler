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
import json
import logging
import os
import sys

import git


def clone(event, output_dir, cache_dir=None):
    try:
        full_name = event.get('repository', {})['full_name']
        clone_url = event.get('repository', {})['clone_url']
    except KeyError:
        raise RuntimeError("Bad event payload")

    refspec = event.get('ref')
    commit = event.get('after')

    if cache_dir:
        cache_git_dir = os.path.join(cache_dir, full_name + '.git')
        cache_git_repo = git.Repo.init(cache_git_dir, bare=True, mkdir=True)

        try:
            cache_git_repo.delete_remote('origin')
        except git.GitCommandError:
            pass

        origin = cache_git_repo.create_remote('origin', clone_url)
        origin.fetch(refspec=refspec)

        working_git_repo = cache_git_repo.clone(output_dir)

        try:
            working_git_repo.delete_remote('origin')
        except git.GitCommandError:
            pass

        origin = working_git_repo.create_remote('origin', clone_url)
        origin.fetch(refspec=refspec)
    else:
        working_git_repo = git.Repo.clone_from(clone_url, output_dir)

    if commit:
        try:
            working_git_repo.head.commit = commit
        except ValueError:
            # can't find the given commit
            raise

    else:
        branch = event.get('repository', {}).get('default_branch', 'master')
        remote_ref = working_git_repo.remotes['origin'].refs[branch]

        try:
            head = working_git_repo.heads[branch]
        except IndexError:
            head = working_git_repo.create_head(branch, remote_ref.commit)
        else:
            head.commit = remote_ref.commit

        head.checkout()
        head.set_tracking_branch(remote_ref)

    working_git_repo.head.reset(index=True, working_tree=True)


def main(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument('--cache-dir',
                        dest='cache_dir',
                        default=os.environ.get('GWH_CACHE_DIR'),
                        help='A directory in which to cache downloaded repos')

    parser.add_argument('-o', '--output-dir',
                        dest='output_dir',
                        default=os.path.abspath('repo'),
                        help='The directory to clone into')

    parser.add_argument('event',
                        type=argparse.FileType('r'),
                        default=os.environ.get('GWH_EVENT_FILE',
                                               os.path.abspath('event.json')),
                        nargs='?',
                        help='The event file to read from')

    logging.basicConfig(level=logging.INFO)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    event_data = json.load(args.event)

    clone(event_data, args.output_dir, cache_dir=args.cache_dir)


if __name__ == '__main__':
    main()
