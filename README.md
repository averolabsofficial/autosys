<div align="center">

```
  █████╗  ██╗   ██╗ ████████╗  ██████╗  ███████╗ ██╗   ██╗ ███████╗
 ██╔══██╗ ██║   ██║ ╚══██╔══╝ ██╔═══██╗ ██╔════╝ ╚██╗ ██╔╝ ██╔════╝
 ███████║ ██║   ██║    ██║    ██║   ██║ ███████╗  ╚████╔╝  ███████╗
 ██╔══██║ ██║   ██║    ██║    ██║   ██║ ╚════██║   ╚██╔╝   ╚════██║
 ██║  ██║ ╚██████╔╝    ██║    ╚██████╔╝ ███████║    ██║    ███████║
 ╚═╝  ╚═╝  ╚═════╝     ╚═╝     ╚═════╝  ╚══════╝    ╚═╝    ╚══════╝

```

# 🚀 AutoSys — YOUR PROJECT'S COMMAND CENTER

**One terminal tool. Git + GitHub + project intelligence. Zero ceremony.**

[![Version](https://img.shields.io/badge/version-2.0.2-blue?style=for-the-badge)](https://github.com/averolabsofficial/autosys/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%E2%94%82%20macOS%20%E2%94%82%20Linux-important?style=for-the-badge)](https://github.com/averolabsofficial/autosys)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge)](CONTRIBUTING.md)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen?style=for-the-badge)](https://github.com/averolabsofficial/autosys/actions)


> **AutoSys** grades your project's ship-readiness, catches leaked secrets before they leak, keeps versions in sync, snapshots your work like a time machine — and ships releases with one command. Built for solo devs and teams who love the terminal.

---

## ✨ Why AutoSys?

| 🛡️ **Know before you ship** | ⏱️ **Never lose work again** | 🚢 **Ship in one command** |
|---|---|---|
| `autosys status` grades your repo **A–F** across 18 real checks in 5 categories (Git, Security, Version, Tests, Docs) — git hygiene, secret leaks, version drift, TODO debt & more | `autosys checkpoint` snapshots your **entire project state** — even dirty, uncommitted files — and `restore` brings it back without touching your branch | `autosys finish` runs tests → bumps versions everywhere → writes the changelog → commits → tags → pushes → drafts the GitHub release |

## 🎯 Feature Tour

| Feature | What it does |
|---|---|
| 🏆 **Ship-Readiness Score** | 100-point audit (5 categories × 20) with an A–F grade and a `🚀 SHIP IT` / `🛠 FIX BEFORE SHIPPING` verdict |
| 🕵️ **Secret Scanner** | Detects 25+ secret types — AWS keys, GitHub/GitLab PATs, Slack, Stripe, OpenAI, JWTs, private keys, DB URLs, `.env` files & more |
| 🔄 **Version Drift Killer** | Finds every place your version lives (`pyproject.toml`, `package.json`, `Cargo.toml`, `__init__.py`…) and aligns them with `--fix` |
| 🕰️ **Checkpoints** | Git-native project snapshots that capture **uncommitted work**. List, compare, restore — branch history stays pristine |
| 📖 **History as a Story** | `autosys explain` turns your git log into a readable narrative of what happened and why |
| 🔐 **Secure Login** | GitHub device-flow OAuth — token encrypted with **Windows DPAPI** (never plaintext on disk) |
| 🚀 **One-Command Release** | `autosys finish`: tests → bump → changelog → commit → tag → push → draft GitHub release |
| 🩺 **Doctor** | Full diagnosis with actionable fixes — run it when something feels off |
| 🤖 **Automation-ready** | Every command works non-interactively with `-y` — perfect for scripts & CI |

---

## ⚡ Quick Start

```bash
# 1. Install (Python 3.10+)
pip install autosys

# 2. Jump into any project
cd ~/my-project
autosys init                       # one-time project memory (.autosys/)
autosys status                     # how ready am I to ship?
autosys commit                     # guided commit wizard
autosys finish                     # full release, one command
```

**First 60 seconds:**

```console
$ cd your-project
$ autosys init
✓ Project memory saved — name: your-project, style: conventional
✓ Scaffolded VERSION = 0.1.0 so `autosys status` can track your version.
✓ Committed scaffolded VERSION file.

$ autosys status
┌──────────────────────────────────────────────────────────────────┐
│ Ship-readiness report — /home/you/your-project                   │
└──────────────────────────────────────────────────────────────────┘
Score: 90/100  —  Grade A

  ✓ Git        20/20
  ✓ Security   20/20
  ⚠ Version    15/20
  ✓ Tests      20/20
  ✓ Docs       20/20
┌──────────────────────────────────────────────────────────────────┐
│ 🚀 SHIP IT                                                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📖 Command Cheatsheet

| Command | What it does |
|---|---|
| `autosys` | 🎛️ Interactive menu |
| `autosys init` | 🏗️ Project memory setup (`.autosys/`) |
| `autosys status` / `check` | 🏆 Ship-readiness report — A–F grade |
| `autosys doctor` | 🩺 Full diagnosis with fixes |
| `autosys commit` | ✍️ Commit wizard (type, scope, push, tag) |
| `autosys finish` | 🚢 Release pipeline: tests → bump → changelog → tag → push → release |
| `autosys checkpoint` | 🕰️ Save a project snapshot (dirty files included) |
| `autosys checkpoints` | 📋 List all snapshots |
| `autosys restore` | ⏪ Restore to a snapshot — branch preserved |
| `autosys secrets` | 🕵️ Scan for leaked secrets |
| `autosys drift [--fix]` | 🔄 Detect / align version drift |
| `autosys explain [file]` | 📖 Git history as a story |
| `autosys login` | 🔐 GitHub device-flow login |
| `autosys logout` / `whoami` | 🚪 Sign out / show identity |
| `autosys repos` | 🐙 Browse / clone your repos |
| `autosys repo create <name>` | 🆕 Create a GitHub repo |
| `autosys repo release <owner/name> [tag]` | 📦 Draft a GitHub release |
| `autosys version` | ℹ️ Show version |

**Global flags:** `-y, --yes` accept defaults / skip prompts · `-h, --help` show help · `--no-browser` (login) · `--client-id <id>` (login) · `--fix` (drift)

---

## 🚢 The Release Pipeline (`autosys finish`)

```
 working tree clean
        │
        ▼
   ┌─────────┐    ┌────────────┐    ┌───────────┐    ┌─────────┐    ┌────────────┐    ┌───────────┐
   │  tests  │──▶│ bump patch │──▶│ changelog │──▶│  commit  │──▶│ tag + push │──▶│ GH release │
   └─────────┘    └────────────┘    └───────────┘    └─────────┘    └────────────┘    └───────────┘
   pytest /      pyproject.toml,   auto-generated   chore(release):   vX.Y.Z          draft release
   npm test /    package.json,     from git log     0.1.1            --follow-tags   (needs login)
   make test     Cargo.toml, ...
```

No release checklist. No forgot-to-bump version. No "did I push the tag?" — AutoSys does it all, verifiably.

---

## 🔐 Security Model

- **Token storage:** GitHub OAuth token encrypted with **Windows DPAPI** (`CryptProtectData`, `DPAPI1`-prefixed blob). On non-Windows systems it degrades to file-permission protection with a warning. The raw token is never written in plaintext.
- **Secret scanner:** 25+ regex families + `.env`/key-file detection, bounded scan (skips `.git`, binaries, build dirs).
- **`secrets` command** prints file + line for every hit so you can purge them before pushing.
- 🔒 Found a vulnerability? See **[SECURITY.md](SECURITY.md)** — we take reports seriously.

---

## 📚 Documentation

- 📖 **Full Manual (the book):** [MANUAL.md](MANUAL.md) — every command, config, workflow & troubleshooting
- 🛠️ **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- 🐛 **Issues:** [bug report](.github/ISSUE_TEMPLATE/bug_report.md) · [feature request](.github/ISSUE_TEMPLATE/feature_request.md)
- 📜 **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- 📝 **License:** [MIT](LICENSE)

---

## 📝 GitHub About (copy-paste these)

> **One-liner:** Your project's command center — ship-readiness grading, secret scanning, checkpoints, and one-command releases from your terminal.

> **Tags:** `git` · `github` · `cli` · `devops` · `release-automation` · `secret-scanning` · `productivity` · `developer-tools`

> **Longer:** AutoSys unifies Git, GitHub, and project intelligence in one terminal tool. It grades your ship-readiness (A–F), scans for leaked secrets, detects version drift, snapshots your work like a time machine, and ships full releases with a single command.

---

## 🗺️ Roadmap (ideas welcome!)

- [ ] `autosys sync` — one-command multi-repo status
- [ ] Checkpoint diffs (`restore --diff`) & snapshot browser
- [ ] GitHub Actions workflow generator
- [ ] `autosys blame` for the team (author report)
- [ ] Custom secret patterns (`.autosys/secrets.json`)

---

## 🧑‍💻 Author & License

Built with ❤️ by **Aditya** · Released under the **[MIT License](LICENSE)** · Version **2.0.2**

<p align="center"><sub>AutoSys — YOUR PROJECT'S COMMAND CENTER · No ceremony, just shipped.</sub></p>
</div>
