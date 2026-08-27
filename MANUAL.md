# 📗 AutoSys — The Complete Manual

**Version 2.0.2 · Your Project's Command Center**

> This manual covers every command, every flag, every configuration file, and every workflow AutoSys supports. Read it once, then keep it as a reference. If something is missing or confusing, open an issue — the manual is part of the project.

---

## Table of Contents

1. [About AutoSys](#1-about-autosys)
2. [Installation](#2-installation)
3. [The Big Picture](#3-the-big-picture)
4. [Project Setup — `init`](#4-project-setup--init)
5. [Ship-Readiness — `status` / `check`](#5-ship-readiness--status--check)
6. [Diagnostics — `doctor`](#6-diagnostics--doctor)
7. [Committing — `commit`](#7-committing--commit)
8. [Releases — `finish`](#8-releases--finish)
9. [Checkpoints — `checkpoint` / `checkpoints` / `restore`](#9-checkpoints--checkpoint--checkpoints--restore)
10. [Secret Scanning — `secrets`](#10-secret-scanning--secrets)
11. [Version Drift — `drift`](#11-version-drift--drift)
12. [History as a Story — `explain`](#12-history-as-a-story--explain)
13. [GitHub Integration — `login` / `logout` / `whoami`](#13-github-integration--login--logout--whoami)
14. [GitHub Repos — `repos` / `repo create` / `repo release`](#14-github-repos--repos--repo-create--repo-release)
15. [The Interactive Menu](#15-the-interactive-menu)
16. [Configuration Files](#16-configuration-files)
17. [Environment Variables](#17-environment-variables)
18. [Non-Interactive Mode (`-y`)](#18-non-interactive-mode--y)
19. [Security Model](#19-security-model)
20. [Exit Codes](#20-exit-codes)
21. [Troubleshooting](#21-troubleshooting)
22. [FAQ](#22-faq)
23. [Development](#23-development)

---

## 1. About AutoSys

AutoSys is a single-file Python CLI that unifies **Git**, **GitHub**, and **project intelligence** into one command center. It answers questions developers ask every day:

- *"Is this project actually ready to ship?"* → **`autosys status`**
- *"Did I just commit a secret?"* → **`autosys secrets`**
- *"Why is my version 0.1.0 in one file and 0.2.0 in another?"* → **`autosys drift --fix`**
- *"I made a mess — can I undo to five minutes ago, including uncommitted changes?"* → **`autosys checkpoint` / `autosys restore`**
- *"What changed in this repo last week?"* → **`autosys explain`**
- *"How do I release v0.1.1 without forgetting something?"* → **`autosys finish`**

Design goals:

- **One file, zero framework.** `autosys.py` — read it, fork it, trust it.
- **Git-native.** Checkpoints are real git objects, not database rows. Nothing is hidden from `git log`.
- **Rich but lightweight.** Beautiful terminal output via `rich`, powered by plain `subprocess` + `requests`.
- **Automation-ready.** `-y` makes every command non-interactive for scripts and CI.

---

## 2. Installation

### Requirements

| Dependency | Minimum | Notes |
|---|---|---|
| Python | 3.10+ | Tested through 3.14 |
| `rich` | 13.0 | Terminal rendering |
| `requests` | 2.28 | GitHub API + device flow |
| `git` | 2.20+ | Any recent version |

### Via pip (recommended)

```bash
pip install autosys
```

Make it invocable from anywhere:

**Windows** — add the `autosys` folder to `PATH`, then run `autosys` (the `.bat` launcher) or `autosys.py` directly:

```bat
:: one-time: add to your user PATH
setx PATH "%PATH%;C:\path\to\autosys"
```

**macOS / Linux** — symlink the launcher:

```bash
chmod +x autosys
ln -s "$(pwd)/autosys" ~/.local/bin/autosys
```

### From source (for development)

```bash
git clone https://github.com/averolabsofficial/autosys.git
cd autosys
pip install -r requirements.txt   # or: pip install requests rich
```

> **Note on the PyPI name:** `autosys` may collide with a legacy job-scheduler tool of the same name on PyPI. If the name is taken, publish under `autosys-cli` and update `[project.scripts]` in `pyproject.toml` accordingly.

### Verify

```bash
autosys version
# AutoSys 2.0.2 — YOUR PROJECT'S COMMAND CENTER
```

---

## 3. The Big Picture

```
┌────────────────────────────────────────────────────────────────────┐
│                        AUTOSYS COMMAND CENTER                      │
├───────────────┬──────────────────────────────┬─────────────────────┤
│  UNDERSTAND   │  PROTECT                     │  SHIP               │
│  status       │  secrets                     │  commit             │
│  doctor       │  checkpoint / restore        │  finish             │
│  drift        │  login (DPAPI-secured)       │  repo release       │
│  explain      │                              │  repo create        │
└───────────────┴──────────────────────────────┴─────────────────────┘
```

Three mental models:

1. **UNDERSTAND** — commands that read your repo and tell you the truth (status, doctor, drift, explain).
2. **PROTECT** — commands that keep you from losing work or leaking secrets (checkpoint/restore, secrets, secure login).
3. **SHIP** — commands that turn a dirty tree into a published release (commit, finish, repos).

Almost every command operates on **the current git repository** (the folder you're standing in). Commands that need GitHub (`repos`, `repo create`, `repo release`, remote status checks) additionally require `autosys login`.

---

## 4. Project Setup — `init`

```bash
autosys init          # interactive
autosys init -y       # defaults: name = folder name, desc = "", style = conventional
```

Creates `.autosys/project.json` — the project's "memory":

```json
{
  "name": "demo-project",
  "description": "",
  "commit_style": "conventional"
}
```

What AutoSys uses this for:

- **`status`** — "Project memory" readiness check.
- **`commit`** — remembers your commit-message style (currently `conventional`).
- **`doctor`** — reports which project you're in.

`-y` behavior: uses the folder name as project name, empty description, and `conventional` commit style. (Earlier builds ignored `-y` here and hung on a TTY — fixed in 2.0.0.)

---

## 5. Ship-Readiness — `status` / `check`

```bash
autosys status        # or: autosys check
```

Runs **13 checks** and grades the repo:

| # | Check | Fail means |
|---|---|---|
| 1 | Git repo initialized | You're not in a git repo |
| 2 | Git identity set | `user.name`/`user.email` missing |
| 3 | Working tree clean | Uncommitted changes pending |
| 4 | In sync with origin | Ahead (push) or behind (pull) |
| 5 | Version files consistent | Drift between version files |
| 6 | No leaked secrets | A secret pattern matched |
| 7 | README present | No README for humans |
| 8 | License present | No LICENSE (important for publishing) |
| 9 | `.env` ignored | `.env` exists but isn't in `.gitignore` |
| 10 | No files >10MB | A tracked file is larger than 10MB (likely a build artifact or binary) |
| 11 | No TODO markers | Actionable marker annotations (keyword followed by a colon or paren) in code |
| 12 | CI green | Failing/pending check runs (needs auth + remote) |
| 13 | Project memory | Run `autosys init` |

**Grading:**

| Score | Grade | Verdict |
|---|---|---|
| ≥ 90 | **A** | 🚀 SHIP IT |
| ≥ 75 | **B** | 🚀 SHIP IT |
| ≥ 60 | **C** | 🛠 FIX BEFORE SHIPPING |
| ≥ 40 | **D** | 🛠 FIX BEFORE SHIPPING |
| < 40 | **F** | 🛠 FIX BEFORE SHIPPING |

**Exit code:** `0` for A/B, `1` for C–F — script-friendly (fails your pipeline when the repo isn't shippable).

Example output:

```console
$ autosys status
┌────────────────────────────────────────────────────────────────────┐
│ Ship-readiness report — /home/you/demo-project                     │
└────────────────────────────────────────────────────────────────────┘
Readiness: B (85/100 — 11/13 checks pass)
┌───────────────────────────┬────────┬───────────────────────────────┐
│ Check                     │ Result │ Detail / Fix                  │
├───────────────────────────┼────────┼───────────────────────────────┤
│ Git repo initialized      │  PASS  │                               │
│ Git identity set          │  PASS  │ You <you@x.com>               │
│ Working tree clean        │  FAIL  │ 2 pending change(s)           │
│ In sync with origin       │  PASS  │ main == origin/main           │
│ Version files consistent  │  PASS  │ 2 file(s) at 0.1.0            │
│ No leaked secrets         │  PASS  │                               │
│ README present            │  PASS  │                               │
│ License present           │  FAIL  │ → Add a LICENSE file before publishing │
│ .env ignored              │  PASS  │                               │
│ No files >10MB            │  PASS  │                               │
│ No TODO markers           │  PASS  │                               │
│ CI green                  │  PASS  │ not checked (no remote/auth)  │
│ Project memory (.autosys) │  PASS  │ demo-project                  │
└───────────────────────────┴────────┴───────────────────────────────┘
┌────────────────────────────────────────────┐
│ 🛠 FIX BEFORE SHIPPING                     │
└────────────────────────────────────────────┘
```

> **Tip:** CI check (#12) only runs when you have a GitHub-style origin remote **and** are logged in. Otherwise it reports "not checked" and counts as a pass so local-only workflows aren't penalized.

---

## 6. Diagnostics — `doctor`

```bash
autosys doctor        # interactive
autosys doctor -y     # non-interactive
```

A full health check of **both** your machine and the current project:

- `git` installed? version?
- Git identity configured?
- Inside a git repo? Project memory present?
- Origin remote (GitHub-style)?
- GitHub auth present? which user?
- OAuth client ID: default (GitHub CLI public) or your own?
- Python version, `rich`/`requests` importable?
- Auth storage initialized?

Ends with an **Action items** panel of concrete fixes. Exit code is always `0` (it's a report, not a gate).

---

## 7. Committing — `commit`

```bash
autosys commit              # full wizard
```

`-y` picks sensible defaults: it stages everything, builds a conventional-commit message (`chore:` with no scope), commits, and pushes. Interactive mode walks you through:

1. **Type** — pick from conventional types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
2. **Scope** (optional) — e.g. `commit -y` equivalents: `feat(auth): ...`
3. **Short summary** — imperative mood, ≤ 72 chars.
4. **Stage & commit** — `git add -A` + commit with the composed message.
5. **Push?** — yes/no. `-y` implies push.
6. **Tag?** — optionally tag the commit (interactive only).

The wizard validates your message against the conventional-commit regex and refuses to commit a malformed message.

---

## 8. Releases — `finish`

```bash
autosys finish              # interactive release pipeline
autosys finish -y           # patch bump, everything default
```

The flagship command. Runs a complete release pipeline with preflight guards:

```
preflight (clean tree?) → tests → version bump → CHANGELOG → commit → tag → push → GitHub release
```

**Step by step:**

| Step | What happens | Fails when |
|---|---|---|
| 0. Preflight | Refuses to run with uncommitted changes | `Working tree is dirty — commit everything first` |
| 1. Tests | Detects runner: `pytest` (pyproject/pytest.ini/tox.ini), `npm test` (package.json), `make test` (Makefile) | Tests fail → abort (last 400 chars of output shown) |
| 2. Bump | Picks current version (primary version file or latest tag), asks bump kind (patch/minor/major); `-y` → patch | — |
| 3. Rewrite versions | Updates **every** detected version file to the new version | File kind not auto-bumpable → manual bump error |
| 4. CHANGELOG | Auto-generates from git log since the latest tag, writes `CHANGELOG.md` | — |
| 5. Commit | `chore(release): X.Y.Z` | Commit fails → abort |
| 6. Tag + push | `vX.Y.Z` tag, `git push --follow-tags` | Push fails → instructions printed, exit 1 |
| 7. GitHub release | If logged in + remote: creates a **draft** release with the changelog body | Not logged in → warning, skipped (local release still complete) |

**Version files AutoSys understands** (drift + finish):

| File | Version location |
|---|---|
| `pyproject.toml` | `version = "..."` |
| `package.json` | `"version": "..."` |
| `Cargo.toml` | `[package] version` |
| `setup.py` | `version="..."` |
| `setup.cfg` | `version = ...` |
| `VERSION` / `version.txt` | file contents |
| `__init__.py` | `__version__ = "..."` |
| `package-lock.json` | `"version"` |

> **Changelog format:** conventional-commit aware — groups by `Features` / `Bug Fixes` / `Other`, links commit hashes, and links `New:` entries. Reused as the GitHub release body (truncated to 4000 chars).

---

## 9. Checkpoints — `checkpoint` / `checkpoints` / `restore`

AutoSys's answer to "I wish I had a time machine." Unlike `git stash`, checkpoints:

- Capture **uncommitted AND untracked** work (via `git add -A` + `git write-tree`).
- Are **named, listed, and restorable** — you can have many.
- Live as real git objects under `refs/autosys/checkpoint-<timestamp>`.
- **Never move your branch.** Restoring puts the snapshot's files back and stages the reverts, but `git log` stays untouched.

### Save a checkpoint

```bash
autosys checkpoint
# e.g. message: "checkpoint 10:02"  (or custom)
# ✓ Snapshot saved — sha 813dd62deccaf80239a76cbc0cd59fafaf46c7f2
# ✓ ref refs/autosys/checkpoint-1787805126
```

What happens under the hood (v2.0.0 semantics):

1. `git add -A` — stage everything, including untracked files.
2. `git reset -q -- .autosys/checkpoints.json` — **exclude the checkpoint index itself** from the snapshot (so the index never self-references a `pending` sha).
3. `git write-tree` — create the tree object of the current worktree state.
4. `git commit-tree` with parent `HEAD` — a full snapshot commit.
5. Store `{sha, ref, timestamp, message}` in `.autosys/checkpoints.json`.
6. `git reset` (plain) — unstage everything; worktree left exactly as it was.

> **Fixed in 2.0.0:** snapshots previously used `commit-tree HEAD^{tree}` which **ignored staged changes** — the snapshot silently captured stale content. Now the snapshot always reflects the real worktree.

### List checkpoints

```bash
autosys checkpoints
# ┌────────────────────────────────────────────────────┐
# │ # │ sha (short) │ ref                          │ time │ msg │
# │ 1 │ 813dd62dec  │ refs/autosys/checkpoint-...  │ ...  │ 10:02│
# └────────────────────────────────────────────────────┘
```

### Restore

```bash
autosys restore        # pick from a numbered list
autosys restore -y     # restore the most recent checkpoint
```

1. Loads the checkpoint index, you pick a snapshot (or the latest with `-y`).
2. Captures `orig = git rev-parse HEAD` — **your branch tip is remembered**.
3. `git reset --hard <snapshot-sha>` — files revert to the snapshot state.
4. `git reset --soft <orig>` — branch tip moved back, all snapshot-vs-branch differences appear **staged**.
5. Result: your files match the snapshot, your branch history is untouched, and `git status` shows the reverts staged and ready to commit (or discard).

> **Fixed in 2.0.0:** restoring previously left your branch tip sitting on the snapshot commit (`HEAD: autosys checkpoint: …`). The two-step `reset --hard` + `reset --soft` dance preserves the branch while applying the snapshot.

> **Gotcha:** `restore --hard`-style semantics mean any work you made **after** the checkpoint in the same files is overwritten in the worktree (it's still recoverable from git reflog). Confirm carefully when prompted.

---

## 10. Secret Scanning — `secrets`

```bash
autosys secrets
```

Scans the repo (bounded: skips `.git`, binaries, images, lock files, build dirs) for **25+ secret families**:

- **Cloud:** AWS Access/Secret keys, Google API keys, Google OAuth client secrets, Stripe (`sk_live_`/`rk_live_`), Twilio, SendGrid, Mailgun, Heroku
- **Code hosting:** GitHub PAT (`ghp_`), fine-grained PAT (`github_pat_`), OAuth (`gho_`), GitLab PAT (`glpat-`)
- **Messaging:** Slack tokens (`xoxb/xoxa/xoxp/xoxr`) and webhooks
- **AI:** OpenAI (`sk-...`), Anthropic (`sk-ant-...`)
- **Databases:** Postgres/MySQL/Mongo/Redis URLs with credentials
- **Crypto/identity:** Private key blocks (`-----BEGIN ... PRIVATE KEY-----`), JWTs, generic `Bearer` tokens
- **Env hygiene:** committed `.env`-style `KEY=value` assignments; flagging of known secret file names (`.env*`, `id_rsa`, `credentials.json`, `secrets.json`)

Output: a table of `file : line : kind : matched-prefix` so you can purge each hit. Exit code `0` if clean, `1` if findings. `status` runs this in quiet mode as check #6.

> **Not a substitute for `gitleaks`/`trufflehog`:** AutoSys scans the current worktree, not history. For leaked-secrets-in-history, run a dedicated tool.

---

## 11. Version Drift — `drift`

```bash
autosys drift          # report drift across all version files
autosys drift --fix    # align everything to the primary version
```

Shows every detected version file with its current value, then the primary version (first of: `pyproject.toml` → `package.json` → `Cargo.toml` → `setup.py` → `setup.cfg` → `__init__.py` → `VERSION` → `version.txt` → `package-lock.json`).

`--fix` rewrites the non-matching files to the primary version. Runs safely (only the version strings change), and `finish` uses the same machinery, so the two are always consistent.

---

## 12. History as a Story — `explain`

```bash
autosys explain              # whole history
autosys explain path/to/file # just that file's story
```

Reads the git log and renders it as a readable narrative — commit type, scope, subject, author, date — grouped by recency. It's `git log --oneline` with personality and structure.

---

## 13. GitHub Integration — `login` / `logout` / `whoami`

### Login (device flow)

```bash
autosys login                      # opens browser automatically
autosys login --no-browser         # just print the code + URL
autosys login --client-id YOUR_ID  # custom OAuth app
```

AutoSys uses the **GitHub device flow**: no username/password, no PAT pasting.

1. Requests a device code + user code from GitHub.
2. Opens your browser to `https://github.com/login/device` (or prints the URL with `--no-browser`).
3. You enter the code (e.g. `5BCB-5CC7`) and authorize.
4. AutoSys polls until authorized, stores the token, and prints your identity.

**Token storage:**

- **Windows:** encrypted with DPAPI (`CryptProtectData`) — file header `DPAPI1`, token never in plaintext. Verified with a round-trip test: plaintext not visible on disk, corrupted blob degrades safely to `{}`.
- **macOS/Linux:** falls back to file-permission protection with a warning.

**The OAuth client ID question — important for production use:**

- Default: GitHub CLI's **public** client ID (`178c6fc778ccc68e1d6a`) so AutoSys works out of the box for development. GitHub may rate-limit or revoke the default — do not build production distributions on it.
- **Production:** register your own OAuth app (GitHub → Settings → Developer settings → OAuth Apps, *no callback URL needed for device flow*), then either:
  - `setx AUTOSYS_CLIENT_ID <your-id>` (Windows) / `export AUTOSYS_CLIENT_ID=<your-id>` (macOS/Linux), or
  - `autosys login --client-id <your-id>` per login.
- Scope requested: `repo workflow read:org`.

### Logout / whoami

```bash
autosys whoami     # "Logged in as <login>" or "Not logged in." (exit 0)
autosys logout     # deletes the stored token
```

---

## 14. GitHub Repos — `repos` / `repo create` / `repo release`

All require login (`autosys login`). Without auth: `✗ Not logged in — run autosys login first.` (exit 1).

### `repos` — browse & clone

```bash
autosys repos
```

Lists your repos (up to 5 pages × 100, sorted by recent activity), shows stars/forks/language/private flags, and lets you **clone** one straight from the list.

### `repo create <name>`

```bash
autosys repo create my-cool-project
```

Creates a GitHub repo via the API (`auto_init: true`, so it ships with a README), prints the clone URL, and offers to clone it locally. Flags: private/public (interactive), description (interactive).

### `repo release <owner/name> [tag]`

```bash
autosys repo release averolabsofficial/repo v0.1.1
autosys repo release                 # reads origin remote, asks for tag
```

Creates a **draft** GitHub release. Tag defaults to the latest semver tag in the current repo. Body: optional message. Drafts are perfect for review-before-publish.

---

## 15. The Interactive Menu

Run `autosys` with no arguments:

```
┌────────────────────────────────────────────────────┐
│  █████╗ ██╗   ██╗████████╗ ██████╗ ███████╗ ...    │
│  AutoSys v2.0.2 — YOUR PROJECT'S COMMAND CENTER    │
└────────────────────────────────────────────────────┘
  1. status      ship-readiness report
  2. commit      commit wizard
  3. secrets     scan for leaked secrets
  4. drift       detect version drift
  5. checkpoint  save snapshot
  6. checkpoints list snapshots
  7. restore     restore snapshot
  8. explain     git history as a story
  9. doctor      full diagnosis
 10. finish      release pipeline
 11. repos       GitHub repos
 12. init        project memory
 13. whoami      login status
 14. logout      sign out
  0. exit
```

Pick a number; the menu dispatches to the same commands as the CLI.

---

## 16. Configuration Files

| Path | Purpose |
|---|---|
| `~/.autosys/config.json` | Global config: `workspace`, `current` project, `cache`, `user` |
| `~/.autosys/auth.json` | GitHub token — **DPAPI-encrypted on Windows** (header `DPAPI1`) |
| `<project>/.autosys/project.json` | Project memory (name, description, commit_style) |
| `<project>/.autosys/checkpoints.json` | Checkpoint index: `{"checkpoints": [{sha, ref, timestamp, message}]}` |
| `refs/autosys/checkpoint-*` | Git refs holding snapshot commits |

All are plain JSON (except the auth blob) — inspect anything, back up `~/.autosys` freely. Corrupted files degrade safely: bad auth blob → `{}` (treated as logged out), missing index → `[]`.

---

## 17. Environment Variables

| Variable | Effect |
|---|---|
| `AUTOSYS_CLIENT_ID` | OAuth client ID for `login` (overrides the GitHub CLI public default) |
| `AUTOSYS_GH_API` | GitHub API base URL (default `https://api.github.com` — handy for GHES or proxies) |
| `NO_COLOR` (standard) | Rich auto-detects; set to disable color |

---

## 18. Non-Interactive Mode (`-y`)

Every command accepts `-y` / `--yes`. Semantics: **accept the safe default at every prompt.**

| Command | `-y` behavior |
|---|---|
| `init` | name=folder, desc="", style=conventional |
| `commit` | stage all → `chore:` commit → push |
| `checkpoint` | default message (timestamp) |
| `restore` | most recent checkpoint |
| `finish` | run tests → patch bump → write changelog → commit/tag/push → skip GH release if no auth |
| `status/doctor/secrets/…` | same output, no interaction |

> **Fixed in 2.0.0:** several commands previously ignored `-y` and blocked on prompts (notably `init`, `checkpoint`, `restore` confirmations). All prompts now route through the `yes`-aware path — verified under a real TTY and via pipes.

Scripting example:

```bash
autosys init -y && autosys commit -y && autosys finish -y
```

---

## 19. Security Model

1. **Token at rest:** DPAPI-encrypted on Windows (verified round-trip; plaintext not present on disk). Fallback on other OSes: file permissions + explicit warning. Token is only readable by the current Windows user.
2. **Token in transit:** device flow uses GitHub's official endpoints over HTTPS; the token is only ever sent to `api.github.com` (or `AUTOSYS_GH_API`).
3. **Secret scanning:** regex-based worktree scan, bounded to avoid pathological repos (`MAX_SCAN_FILE` size, `MAX_SCAN_FILES` count, skip lists). Findings report file:line so you can verify before acting.
4. **No telemetry.** AutoSys phones home nowhere. All state is local files you can read.
5. **Report vulnerabilities** to the project via SECURITY.md — never in public issues.

---

## 20. Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success (or benign report: `whoami` not-logged-in, `doctor` report, `status` grade A/B) |
| `1` | Hard failure: bad usage, dirty-tree release preflight, test failures, push failure, auth gate (`repos` etc. while logged out), `status` grade C–F, secrets found |

Scripts should rely on these: `autosys status -y || echo "not shippable"` → fails CI when the repo isn't ready.

---

## 21. Troubleshooting

### `init -y` hangs waiting for input
→ 2.0.0+ honors `-y` (no prompts). On older builds, press Ctrl+C, upgrade.

### `Not inside a git repository — cd into a project first.`
→ `status/commit/secrets/drift/checkpoint/restore/explain/finish` need a git repo. Run `git init` first (or `cd` into the right folder).

### `Not logged in — run autosys login first.`
→ GitHub features (`repos`, `repo create`, `repo release`, CI checks) need `autosys login`. The local pipeline (`commit/finish/checkpoint/…`) works without it.

### Login prints "OAuth app not configured" / uses the public client ID
→ Expected for the default client. Set `AUTOSYS_CLIENT_ID` to your own OAuth app for production use (see §13).

### `autosys finish` aborts: "Working tree is dirty"
→ Intended. `autosys commit` (or `git commit`) first; releases start from a clean tree.

### Tests fail inside `finish` but pass standalone
→ `finish` runs `python -m pytest -q` from the project root with a 600s timeout. Check for environment-dependent tests, network access, or missing dev deps in the runner's environment.

### `restore` shows staged reverts — did it break my branch?
→ No. Restoring stages the differences between your branch and the snapshot; commit them to keep, or `git reset` to discard. Your branch history is untouched.

### Checkpoints show old content
→ 2.0.0 fixes snapshot capture (write-tree instead of `HEAD^{tree}`). Re-save the checkpoint after upgrading; old snapshots remain valid objects, just possibly stale.

### CRLF warnings from git on Windows
→ Cosmetic. Set `core.autocrlf` per your team convention; AutoSys is agnostic.

### Color/unicode artifacts in CI logs
→ Run with `NO_COLOR=1` or `TERM=dumb`; Rich degrades gracefully.

### Something crashed?
→ File an issue with: OS + Python version, exact command, full output, and (if safe) your `~/.autosys` file listing.

---

## 22. FAQ

**Is this a wrapper around GitHub CLI?**
No. AutoSys talks to the GitHub REST API directly (`requests`) and to git directly (`subprocess`). It reuses GitHub CLI's *public client ID* by default purely so the OAuth device flow works without setup.

**Do I need a GitHub account to use AutoSys?**
No. `status`, `commit`, `checkpoint`, `restore`, `secrets`, `drift`, `explain`, `finish` (local part) all work offline. GitHub features need login.

**Where do checkpoints live? Are they pushed?**
They're local git refs (`refs/autosys/checkpoint-*`) + a local JSON index. They never touch `origin` — your team won't see your private snapshots.

**Can AutoSys auto-bump anything?**
Anything in the version-file matrix (§8). Unsupported layouts (e.g. `Chart.yaml`, `*.csproj`) report a clear "bump manually" error rather than corrupting files.

**Does `finish` create GitHub releases automatically?**
Only if you're logged in, and always as **drafts** — publish manually after review.

**What if PyPI already has "autosys"?**
Rename the distribution to `autosys-cli` in `pyproject.toml` (`[project] name`) — the console command stays `autosys`.

**Will AutoSys ever send my code anywhere?**
No. All analysis is local. GitHub API calls only carry auth + repo references for the features you invoke.

---

## 23. Development

```bash
git clone https://github.com/averolabsofficial/autosys.git
cd autosys
python -m py_compile autosys.py          # syntax gate
python autosys.py --help                 # smoke test
```

**Architecture:** single module, ~2,200 lines:

- `git()` — central subprocess wrapper (cwd-scoped, typed output)
- Rich `console` / `err_console` for all rendering
- `SecureStore` — DPAPI auth storage
- `GitHubAPI` — REST client (auth, repos, releases, check-runs)
- `run_check()` — the 13-point status engine
- `scan_secrets()` — bounded regex engine
- `detect_version_files()` / `set_version()` — drift + bump machinery
- `cmd_*` — one function per command, dispatched from `main()`

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full developer guide. Tests, docs, and issue templates are welcome — PRs are reviewed fast.

---

<p align="center"><sub>AutoSys 2.0.2 · Your Project's Command Center · MIT License</sub></p>
