"""Regression test: init_session must honor constructor-supplied cwd.

Prior bug: the bootstrap script captured env vars and wrote ``pwd -P``
to a temp file *without* cd'ing to ``self.cwd`` first. The bash
subprocess inherited Python's ``os.getcwd()`` (typically the gateway
launch dir), the temp file got that unrelated path, and the subsequent
``_update_cwd()`` clobbered ``self.cwd``. Result: profile-scoped
``TERMINAL_CWD`` settings were silently overridden by whatever dir the
parent process happened to live in.
"""

import os
import tempfile

import pytest

from tools.environments.local import LocalEnvironment


@pytest.fixture
def other_dir(tmp_path):
    target = tmp_path / "profile-workspace"
    target.mkdir()
    return target


def test_init_session_preserves_constructor_cwd(other_dir, monkeypatch):
    # Pin Python's cwd somewhere unrelated to ``other_dir`` so the bug
    # (inheriting parent cwd) would produce a distinct, detectable value.
    with tempfile.TemporaryDirectory() as parent_cwd:
        monkeypatch.chdir(parent_cwd)
        env = LocalEnvironment(cwd=str(other_dir), timeout=10)
        try:
            assert env.cwd == str(other_dir), (
                f"init_session clobbered self.cwd: expected {other_dir!s}, "
                f"got {env.cwd!r}"
            )
            # And a fresh pwd through execute() must also report the
            # caller-supplied dir, not the parent process cwd.
            result = env.execute("pwd", timeout=10)
            assert result.get("output", "").strip() == str(other_dir)
        finally:
            env.cleanup()
