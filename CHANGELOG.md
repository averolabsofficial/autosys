# Changelog

All notable changes to **AutoSys** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [Unreleased]

- Planned: multi-repo `sync`, checkpoint diffs (`restore --diff`), Actions workflow generator, custom secret patterns, author blame reports.

## [2.0.1] — 2026-08-27

### Fixed

- **Secret scanner self-matches** — the `MySQL URL` and `Redis URL` patterns matched their own literal definitions inside `autosys.py` (e.g. `mysql://[^:\s]+:[^@\s]+@[^\s]+` was reported as a leaked credential). URL username character classes are now tightened to `[A-Za-z0-9_.-]` so a pattern can never match its own source text; the `Postgres URL` and `Mongo URL` patterns were hardened the same way.
- **`.env committed` false positives on code** — the generic `.env` pattern flagged Python assignments like `auth = load_auth()` as leaked secrets. Values that are function calls (`identifier(...)`) are now excluded.
- **TODO marker noise** — the "No TODO markers" check counted the words TODO/FIXME/HACK anywhere in a file, including the tool's own documentation and check descriptions (15 false positives on this repo alone). It now only counts actionable annotations (`TODO:`, `FIXME(`, `HACK[` etc.) so prose mentions no longer fail the grade.

## [2.0.0] — 2026-08-27

First public release — the "it actually works everywhere" release.

### Added

- **Ship-readiness report** (`status` / `check`) — 13-point audit with A–F grade, `SHIP IT` / `FIX BEFORE SHIPPING` verdict, and script-friendly exit codes.
- **Secret scanner** (`secrets`) — 25+ secret families (AWS, GitHub/GitLab PATs, Slack, Stripe, OpenAI, JWTs, private keys, DB URLs, `.env` hygiene), file:line reporting.
- **Version drift detection** (`drift`, `drift --fix`) — detects and aligns every version file in the project (pyproject.toml, package.json, Cargo.toml, setup.py/cfg, `__init__.py`, VERSION, package-lock.json).
- **Checkpoints** (`checkpoint` / `checkpoints` / `restore`) — git-native project snapshots that include dirty and untracked files; branch-preserving restore.
- **Release pipeline** (`finish`) — tests → version bump → auto-CHANGELOG → commit → tag → push → draft GitHub release, with dirty-tree and failing-test preflight guards.
- **Commit wizard** (`commit`) — conventional-commit validation, scopes, push + tag options.
- **Doctor** (`doctor`) — full environment + project diagnosis with action items.
- **History as a story** (`explain [file]`) — readable git-log narrative.
- **GitHub integration** — device-flow login with DPAPI-encrypted token storage (Windows), `whoami`/`logout`, `repos` browse+clone, `repo create`, `repo release` (draft releases).
- **Interactive menu** — rich terminal UI when run without arguments.
- **Non-interactive mode** — `-y`/`--yes` on every command for scripts and CI.

### Fixed

- **`init -y` hung on a TTY** — the prompt was shown even when `yes` was passed; `cmd_init` now uses defaults (`name = folder`, `desc = ""`, `style = conventional`) under `-y`.
- **Checkpoint snapshots ignored staged changes** — the snapshot used `git commit-tree HEAD^{tree}`, capturing the last commit's tree instead of the real worktree. Now uses `git add -A` + `git write-tree`, so dirty state is always captured.
- **Checkpoint rewound branch history** — the old `git reset --soft HEAD^{}` after snapshotting moved the branch tip; replaced with a plain `git reset` (unstage only).
- **Checkpoint index crash** — `_save_checkpoints(root, cps + [cp])` discarded the new list, then `cps[-1]["sha"] = sha` raised `IndexError: list index out of range` (and could overwrite the previous entry's sha). The list is now correctly reassigned.
- **Checkpoint index self-poisoning** — the snapshot captured `checkpoints.json` with `sha: "pending"`; a later `restore --hard` made the index stale and caused `KeyError: 'ref'`. The index is now excluded from snapshots (`git reset -q -- .autosys/checkpoints.json` after `add -A`).
- **Restore polluted the branch** — `git reset --hard <snap>` parked the branch tip on the snapshot commit. Restore now captures `HEAD`, resets to the snapshot, then `reset --soft` back to the original tip: files restored, branch preserved, reverts staged.
- **`-y` inconsistent on checkpoint/restore confirmations** — confirmations bypassed the `yes` flag; all prompts now route through the `yes`-aware path.
- **SecureStore cleanup** — test harness closed the `mkstemp` file descriptor to avoid a Windows file-lock on deletion.
- **pip entry point crashed** — the console script calls `main()` with no arguments but `main(argv)` required one, so `pip install autosys` produced a binary that died with `TypeError` on first run. `main()` now defaults to `sys.argv` when called without arguments (found by an install→run→uninstall packaging test).

### Security

- GitHub token encrypted with **Windows DPAPI** (`CryptProtectData`, `DPAPI1` blob header) — verified: plaintext never on disk, corrupted blob degrades to `{}`.
- Production OAuth guidance: `AUTOSYS_CLIENT_ID` env var and `login --client-id` for registering your own OAuth app; default is GitHub CLI's public client ID for out-of-the-box development use only.
