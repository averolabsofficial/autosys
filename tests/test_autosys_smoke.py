"""Smoke tests for AutoSys — pure-local, no network, no auth.

Covers the scanner regressions fixed in 2.0.1 (self-matches, .env
function-call false positives, actionable-only TODO counting) plus the
version invariant and run_check behaviour in a fresh git repo.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import autosys  # noqa: E402


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.name", "Test User")
    git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".autosys/\n__pycache__/\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "initial")
    script = str(Path(__file__).resolve().parents[1] / "autosys.py")
    r = subprocess.run([sys.executable, script, "init", "-y"], cwd=tmp_path,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return tmp_path


def run_status(repo: Path) -> str:
    script = str(Path(__file__).resolve().parents[1] / "autosys.py")
    r = subprocess.run([sys.executable, script, "status", "-y"],
                       cwd=repo, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return r.stdout


def status_row(out: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}\s+(PASS|FAIL)", out)
    assert m, f"check row not found for {name!r}"
    return m.group(1)


# --------------------------------------------------------------------------
# Version invariant
# --------------------------------------------------------------------------

def test_version_is_semver():
    parts = autosys.VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# --------------------------------------------------------------------------
# Secret scanner regressions (fixed in 2.0.1)
# --------------------------------------------------------------------------

def test_scanner_does_not_flag_own_patterns(tmp_path):
    (tmp_path / "patterns.txt").write_text(
        '("MySQL URL", r"mysql://[^:\\s]+:[^@\\s]+@[^\\s]+")\n'
        '("Redis URL", r"redis://[^:\\s]*:[^@\\s]+@[^\\s]+")\n'
        '("Postgres URL", r"postgres(?:ql)?://[^:\\s]+:[^@\\s]+@[^\\s]+")\n'
        '("Mongo URL", r"mongodb(?:\\+srv)?://[^:\\s]+:[^@\\s]+@[^\\s]+")\n',
        encoding="utf-8",
    )
    findings = autosys.scan_secrets(tmp_path, quiet=True)
    kinds = {f["kind"] for f in findings}
    assert not (kinds & {"MySQL URL", "Redis URL", "Postgres URL", "Mongo URL"})


def test_scanner_detects_real_aws_key(tmp_path):
    # Payload split at runtime so the test source itself stays scanner-clean
    # (a contiguous AKIA… token in this file would trip AutoSys's self-scan).
    (tmp_path / "leak.txt").write_text(
        "aws_access_key=" + "AKIA" + "IOSFODNN7EXAMPLE\n", encoding="utf-8")
    findings = autosys.scan_secrets(tmp_path, quiet=True)
    assert any(f["kind"] == "AWS Access Key" for f in findings)


def test_env_pattern_ignores_function_calls(tmp_path):
    (tmp_path / "code.py").write_text("auth = load_auth()\n", encoding="utf-8")
    findings = autosys.scan_secrets(tmp_path, quiet=True)
    assert all(f["kind"] != ".env committed" for f in findings)


def test_env_pattern_still_catches_real_values(tmp_path):
    # Split as above: a contiguous api_key="sk-…" literal would be flagged
    # by the scanner when it reads this very test file.
    (tmp_path / ".env").write_text(
        "api_key = \"" + "sk" + "-real-secret-value-123\"\n", encoding="utf-8")
    findings = autosys.scan_secrets(tmp_path, quiet=True)
    assert any(f["kind"] == ".env committed" for f in findings)


# --------------------------------------------------------------------------
# TODO marker check (fixed in 2.0.1)
# --------------------------------------------------------------------------

def test_todo_check_ignores_prose(repo):
    (repo / "prose.md").write_text(
        "This file mentions a todo list, a hack idea, and chores.\n",
        encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "prose")
    assert status_row(run_status(repo), "No TODO markers") == "PASS"


def test_todo_check_flags_actionable(repo):
    # Split so this file has no literal "TODO:" that the repo self-check counts.
    (repo / "code.py").write_text("# TOD" + "O: implement this\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add todo")
    assert status_row(run_status(repo), "No TODO markers") == "FAIL"


# --------------------------------------------------------------------------
# Status engine sanity
# --------------------------------------------------------------------------

def test_status_reports_grade_a(repo):
    assert "SHIP IT" in run_status(repo)
