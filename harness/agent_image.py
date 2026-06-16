# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Build the per-target agent image: target binary + DeepSeek runner.

The agent runs *inside* its container, so the container needs the runner CLI.
To avoid one Python install per target, ``ensure()`` builds a shared
``vuln-pipeline-agent-base:<runner-version>`` once (gcc:14 + python3 + openai
SDK + deepseek_runner.py installed as ``claude``) and then layers each
target's ``/work`` on top via ``COPY --from``. Target Dockerfiles stay
unchanged (single source of truth for the binary build).
"""

from __future__ import annotations

import functools
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

from . import docker_ops

RUNNER_VERSION = "deepseek-1"
BASE_TAG = f"vuln-pipeline-agent-base:{RUNNER_VERSION}"
_TAG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/:-]*$")


def agent_tag(target_tag: str) -> str:
    """Distinct agent-image tag per *full* target tag, so a committed
    ``<name>:patched-<uuid>`` snapshot doesn't collide with ``<name>:v1``."""
    return f"{target_tag.replace(':', '-')}-agent:{RUNNER_VERSION}"


def _build(dockerfile: str, tag: str, extra_files: dict[str, str] | None = None) -> None:
    with tempfile.TemporaryDirectory() as ctx:
        with open(f"{ctx}/Dockerfile", "w") as f:
            f.write(dockerfile)
        for name, content in (extra_files or {}).items():
            with open(f"{ctx}/{name}", "w") as f:
                f.write(content)
        subprocess.run(
            ["docker", "build", "-q", "-t", tag, ctx],
            check=True,
            capture_output=True,
            text=True,
        )


def _ensure_base() -> str:
    if docker_ops.image_exists(BASE_TAG):
        return BASE_TAG
    # xxd + gdb: the find/patch prompts list these as available. Target
    # Dockerfiles install them too, but ``ensure()`` only copies /work from the
    # target image — apt packages outside /work don't survive the COPY --from.
    # Anything the prompts promise has to live in this base layer.
    runner_src = (Path(__file__).parent / "deepseek_runner.py").read_text()
    _build(
        textwrap.dedent("""\
            FROM gcc:14
            RUN apt-get update && \\
                apt-get install -y --no-install-recommends python3 python3-pip \\
                    ca-certificates xxd gdb && \\
                rm -rf /var/lib/apt/lists/* && \\
                pip3 install --break-system-packages openai
            COPY deepseek_runner.py /usr/local/bin/claude
            RUN chmod +x /usr/local/bin/claude
            WORKDIR /work
        """),
        BASE_TAG,
        extra_files={"deepseek_runner.py": runner_src},
    )
    return BASE_TAG


@functools.lru_cache(maxsize=None)
def ensure(target_tag: str) -> str:
    """Build (if missing) and return the agent-image tag for ``target_tag``."""
    if not _TAG_RE.match(target_tag):
        raise ValueError(f"invalid image tag: {target_tag!r}")
    tag = agent_tag(target_tag)
    if docker_ops.image_exists(tag):
        return tag
    _ensure_base()
    _build(
        f"FROM {BASE_TAG}\nCOPY --from={target_tag} /work /work\n",
        tag,
    )
    subprocess.run(
        ["docker", "tag", tag, f"{tag.rsplit(':', 1)[0]}:latest"],
        check=True,
    )
    return tag
