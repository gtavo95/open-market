"""Looks for keys in what git sees of the repo: what is committed and what is new that `.gitignore` does not ignore.

It is the `secret-scan` of `just ci`. Each finding comes out as
`file:line: rule: what it is`, without the value: the ci output stays in logs and PRs, and copying
the key there would leak it again. It exits 1 if it found something.

A key that shows up is not silenced here: it is taken out of the file and read from an environment variable
(`.env.example` says which). The ones already committed get rotated, because they are still in the history.

The wheels in `vendor/` are opened and each file inside is scanned (`file!member:line`).
`uv.lock` is not: those are package hashes, and any entropy rule would mistake them for keys.
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NOT_READ = {"uv.lock"}


@dataclass(frozen=True)
class Rule:
    name: str
    what: str
    pattern: re.Pattern[str]


_NAME = r"(?:[A-Za-z_][A-Za-z0-9_]*)?(?:KEY|SECRET|TOKEN|PASSWORD|key|secret|token|password)[A-Za-z0-9_]*"

RULES = (
    Rule(
        "meta-token",
        "Meta access token (Graph / WhatsApp Cloud API); it goes in an environment variable",
        re.compile(r"\bEAA[A-Za-z0-9]{30,}"),
    ),
    Rule(
        "openai-key",
        "OpenAI key; it goes in OPENAI_API_KEY",
        re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    ),
    Rule(
        "google-key",
        "Google key (Gemini, Maps, Firebase); it goes in GEMINI_API_KEY or another variable",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
    ),
    Rule(
        "github-token",
        "GitHub token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"),
    ),
    Rule(
        "private-key",
        "private key in PEM",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY"),
    ),
    Rule(
        "assigned-secret",
        "a key variable with the value written in; it goes in an environment variable",
        re.compile(
            rf"^\s*(?:export\s+)?[\"']?{_NAME}[\"']?\s*(?::\s*str\s*)?[:=]\s*"
            r"([\"']?)(?=[A-Za-z0-9_\-./+=]*[0-9])(?=[A-Za-z0-9_\-./+=]*[A-Za-z])[A-Za-z0-9_\-./+=]{16,}\1"
            r"\s*,?\s*(?:#.*)?$"
        ),
    ),
)


@dataclass(frozen=True)
class Finding:
    where: str
    line: int
    rule: Rule

    def __str__(self) -> str:
        return f"{self.where}:{self.line}: {self.rule.name}: {self.rule.what}"


def in_text(where: str, text: str) -> Iterator[Finding]:
    for n, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.pattern.search(line):
                yield Finding(where, n, rule)


def _text(data: bytes) -> str | None:
    """`None` if it is binary: a null byte in the first KB, as git decides it."""
    if b"\0" in data[:1024]:
        return None
    return data.decode("utf-8", errors="replace")


def in_file(root: Path, path: str) -> Iterator[Finding]:
    full_path = root / path
    if Path(path).name in NOT_READ or not full_path.is_file():
        return
    if full_path.suffix in {".whl", ".zip"}:
        with zipfile.ZipFile(full_path) as z:
            for member in z.namelist():
                text = _text(z.read(member))
                if text is not None:
                    yield from in_text(f"{path}!{member}", text)
        return
    text = _text(full_path.read_bytes())
    if text is not None:
        yield from in_text(path, text)


def files(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True,
    ).stdout
    return sorted({r for r in output.decode().split("\0") if r})


def scan(root: Path) -> list[Finding]:
    return [h for path in files(root) for h in in_file(root, path)]


def main() -> int:
    findings = scan(ROOT)
    for h in findings:
        print(h)
    if findings:
        print(f"secret-scan: {len(findings)} findings", file=sys.stderr)
        return 1
    print(f"secret-scan: {len(files(ROOT))} files, no keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
