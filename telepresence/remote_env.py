# Copyright 2018 Datawire. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
from subprocess import CalledProcessError
from time import time, sleep
from typing import Dict

from telepresence.remote import RemoteInfo
from telepresence.runner import Runner


def _get_remote_env(
    runner: Runner, context: str, namespace: str, pod_name: str,
    container_name: str
) -> Dict[str, str]:
    """Get the environment variables in the remote pod."""
    env = runner.get_kubectl(
        context, namespace,
        ["exec", pod_name, "--container", container_name, "env"]
    )
    result = {}  # type: Dict[str,str]
    prior_key = None
    for line in env.splitlines():
        try:
            key, value = line.split("=", 1)
            prior_key = key
        except ValueError:
            # Prior key's value contains one or more newlines
            assert prior_key is not None
            key = prior_key
            value = result[key] + "\n" + line
        result[key] = value
    return result


def get_env_variables(runner: Runner, remote_info: RemoteInfo,
                      context: str) -> Dict[str, str]:
    """
    Generate environment variables that match kubernetes.
    """
    span = runner.span()
    # Get the environment:
    remote_env = _get_remote_env(
        runner, context, remote_info.namespace, remote_info.pod_name,
        remote_info.container_name
    )
    # Tell local process about the remote setup, useful for testing and
    # debugging:
    result = {
        "TELEPRESENCE_POD": remote_info.pod_name,
        "TELEPRESENCE_CONTAINER": remote_info.container_name
    }
    # Alpine, which we use for telepresence-k8s image, automatically sets these
    # HOME, PATH, HOSTNAME. The rest are from Kubernetes:
    for key in ("HOME", "PATH", "HOSTNAME"):
        if key in remote_env:
            del remote_env[key]
    result.update(remote_env)
    span.end()
    return result


def get_remote_env(
    runner: Runner, args: argparse.Namespace, remote_info: RemoteInfo
) -> Dict[str, str]:
    # Get the environment variables we want to copy from the remote pod; it may
    # take a few seconds for the SSH proxies to get going:
    start = time()
    while time() - start < 10:
        try:
            env = get_env_variables(runner, remote_info, args.context)
            break
        except CalledProcessError:
            sleep(0.25)
    else:
        return exit("Error: Failed to get environment variables")
    return env