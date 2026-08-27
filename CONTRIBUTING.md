# Contributing to AutoSys

First off — thanks for wanting to contribute! 🎉 AutoSys is a single-file tool
built to be readable, auditable, and fun to hack on. This guide keeps it that way.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Project Layout](#project-layout)
- [Development Workflow](#development-workflow)
- [Quality Gates](#quality-gates)
- [Testing](#testing)
- [Style Guide](#style-guide)
- [Submitting Changes](#submitting-changes)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

By participating you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).
Be kind, be constructive, be excellent to each other.

## Getting Started

```bash
# Primary: install from PyPI (requires Python 3.10+)
pip install autosys

# Or: run from source
pip install -r requirements.txt  # runtime deps
git clone https://github.com/averolabsofficial/autosys.git
cd autosys
pip install pytest               # dev dep
```

**The golden rule:** AutoSys is *one file*. Before adding code, ask yourself
whether it belongs in `autosys.py` or is better as a thin plugin/reference —
kept small, it stays auditable.

## Project Layout

```
autosys/
├── autosys.py          # the entire tool (~2,200 lines, one file)
├── autosys             # POSIX launcher (exec python autosys.py "$@")
├── autosys.bat         # Windows launcher
├── README.md           # the pitch + cheatsheet
├── MANUAL.md           # the complete manual (keep in sync!)
├── CHANGELOG.md        # Keep a Changelog format
├── SECURITY.md         # vulnerability reporting
├── pyproject.toml      # packaging (pip install autosys)
└── tests/              # pytest suite
```

### Inside `autosys.py`

- `git()` — single subprocess wrapper (cwd-scoped, typed).
- `RichConsole` — all rendering via `rich` (`console` for output, `err_console` for errors).
- `SecureStore` — DPAPI-secured token storage (Windows), permission-fallback elsewhere.
- `GitHubAPI` — REST client: auth, repos, releases, check-runs.
- `run_check()` — the 12-point ship-readiness engine.
- `scan_secrets()` — bounded regex secret scanner.
- `detect_version_files()` / `set_version()` — drift detection + bumping.
- `cmd_<name>()` — one function per command, wired in `main()` and the interactive menu.

## Development Workflow

1. Fork + branch: `git checkout -b feat/my-thing`.
2. Make the change in `autosys.py`.
3. **Test against a scratch repo** — never your real work! Use a temp dir:
   ```bash
   mkdir /tmp/as-test && cd /tmp/as-test && git init
   echo v0.1.0 > VERSION && echo "# x" > README.md
   python ~/autosys/autosys.py init -y
   python ~/autosys/autosys.py status
   ```
4. Run the quality gates (below).
5. Commit with a conventional message: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`.
6. Push and open a PR against `main`.

## Quality Gates

Every PR must pass:

```bash
python -m py_compile autosys.py        # 1. syntax
python autosys.py --help               # 2. help renders
python -m pytest -q                    # 3. tests (if added)
python autosys.py doctor -y            # 4. doctor runs clean
```

**Interactive-path rule:** whenever you change a prompt, re-verify the command
under a real TTY *and* piped (`echo "" | autosys ...`) *and* with `-y`. Prompts
that hang or ignore `-y` are the #1 regression class in this project (see the
2.0.0 changelog).

## Testing

New commands and bug fixes **must** ship with a pytest test in `tests/`.

Recommended patterns (see `tests/` for live examples):

- **CLI smoke tests** — invoke `autosys.main([...])` in-process and assert on output/exit.
- **Pipeline tests** — create a temp git repo, run `init/commit/checkpoint/restore/finish`, assert on `git log`, tags, and file contents.
- **SecureStore tests** — round-trip with a temp file; on Windows assert `DPAPI1` header and no plaintext; corrupt-blob → `{}`.

Windows note: close `mkstemp` fds (`os.close(fd)`) before `unlink()` or you'll
hit `PermissionError [WinError 32]`.

## Style Guide

- Python 3.10+ syntax (`X | None`, `match`, `Path` everywhere — no `os.path`).
- Type hints on every function signature.
- Single quotes for strings; 4-space indent; keep lines ≤ 100 chars.
- Errors go through `fail(...)` (exits 1) or `err_console`; progress via `info/ok/warn`.
- No new third-party dependencies without a strong reason — `requests` + `rich` is the whole stack.
- Every user-facing string is a full sentence — this tool talks to humans.

## Submitting Changes

1. Keep PRs small and focused (one concern per PR).
2. Reference the issue: `Fixes #12`.
3. Update **both** `README.md` (cheatsheet) and `MANUAL.md` (manual) if the command surface changes — docs are part of the deliverable.
4. Add a `CHANGELOG.md` entry under `[Unreleased]`.
5. Screenshots for UI changes are appreciated — the terminal is the product.

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include:

- OS + Python version (`python --version`), git version.
- Exact command and full output (paste, don't paraphrase).
- A minimal reproduction (scratch repo steps preferred).
- Whether it happens with `-y`, piped, or on a real TTY.

## Feature Requests

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).
Explain the problem you're solving, not just the feature — great suggestions
land faster with a concrete workflow example.

---

<p align="center"><sub>Questions? Open a discussion — maintainers watch issues and PRs daily.</sub></p>
