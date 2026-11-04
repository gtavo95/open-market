"""The secret-scan of `just ci`: each rule has a case that sets it off with file and line.

The fake keys are built by gluing pieces together, so that this file is not itself a finding.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts.secret_scan import in_file, scan

FILLER = "Ab1" * 20

KEYS = {
    "meta-token": "EA" + "AB" + FILLER,
    "openai-key": "sk" + "-proj-" + FILLER,
    "google-key": "AI" + "za" + FILLER[:35],
    "github-token": "gh" + "p_" + FILLER[:36],
    "private-key": "-----BEGIN " + "RSA PRIVATE " + "KEY-----",
}


def written(tmp_path: Path, name: str, text: str) -> Path:
    (tmp_path / name).write_text(text)
    return tmp_path


@pytest.mark.parametrize("rule, key", KEYS.items())
def test_each_rule_fires_with_file_and_line_and_without_the_value(tmp_path: Path, rule: str, key: str) -> None:
    root = written(tmp_path, "config.py", f"# nothing\n\nVALUE = '{key}'\n")
    findings = [str(h) for h in in_file(root, "config.py")]
    assert any(h.startswith(f"config.py:3: {rule}: ") for h in findings), findings
    assert not any(key in h for h in findings)


@pytest.mark.parametrize(
    "line",
    [
        "WHATSAPP_TOKEN=" + FILLER,
        "export META_APP_SECRET='" + "0123456789abcdef" * 2 + "'",
        "    client_secret: str = \"" + FILLER + "\"",
        "access_token: " + FILLER,
    ],
)
def test_assigned_secret(tmp_path: Path, line: str) -> None:
    root = written(tmp_path, ".env", "APP_NAME=demo\n" + line + "\n")
    assert [str(h) for h in in_file(root, ".env")] == [
        ".env:2: assigned-secret: a key variable with the value written in; it goes in an environment variable"
    ]


@pytest.mark.parametrize(
    "line",
    [
        "OPENAI_API_KEY=",
        "TYPESAFE_API_KEY=${TYPESAFE_API_KEY}",
        "  --set-secrets OPENAI_API_KEY=PROD_OPENAI_API_KEY:latest \\",
        "DEMO_SECRET = os.environ['DEMO_SECRET']",
        "secret: str = \"s3cr3t\"",
        "MAX_TOKENS = 4096",
        "token = request.headers['Authorization']",
    ],
)
def test_what_is_not_a_key_passes(tmp_path: Path, line: str) -> None:
    root = written(tmp_path, "a.py", line + "\n")
    assert list(in_file(root, "a.py")) == []


def test_inside_a_wheel_it_says_the_member(tmp_path: Path) -> None:
    with zipfile.ZipFile(tmp_path / "x.whl", "w") as z:
        z.writestr("x/config.py", "\nTOKEN = '" + KEYS["meta-token"] + "'\n")
    assert [str(h).split(": ")[0:2] for h in in_file(tmp_path, "x.whl")] == [
        ["x.whl!x/config.py:2", "meta-token"],
        ["x.whl!x/config.py:2", "assigned-secret"],
    ]


def test_binaries_and_uv_lock_are_not_read(tmp_path: Path) -> None:
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\0" + KEYS["meta-token"].encode())
    written(tmp_path, "uv.lock", KEYS["openai-key"] + "\n")
    assert list(in_file(tmp_path, "photo.png")) == []
    assert list(in_file(tmp_path, "uv.lock")) == []


def test_scans_what_is_new_uncommitted_and_not_what_is_ignored(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    written(tmp_path, ".gitignore", ".env\n")
    written(tmp_path, ".env", "WHATSAPP_TOKEN=" + KEYS["meta-token"] + "\n")
    written(tmp_path, "new.sh", "curl -H 'Authorization: Bearer " + KEYS["meta-token"] + "'\n")
    assert [str(h) for h in scan(tmp_path)] == [
        "new.sh:1: meta-token: Meta access token (Graph / WhatsApp Cloud API); it goes in an environment variable"
    ]
