#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoSys — Your project's command center.
A terminal tool that unifies GitHub + Git + project intelligence in one place.

Usage:
  autosys                    interactive menu
  autosys <command> [args]   direct command (see `autosys --help`)

Commands:
  login / logout / whoami    GitHub authentication (device flow, DPAPI-secured)
  init                       one-time project memory setup (.autosys/)
  status | check             ship-readiness report with a score & verdict
  commit                     interactive commit + push + tag wizard
  drift                      detect version drift across the ecosystem
  secrets                    scan repo for leaked secrets
  checkpoint / checkpoints   save / list project state snapshots
  restore                    restore project to a checkpoint
  explain [file]             git history as a story
  doctor                     full diagnosis with suggested fixes
  finish                     end-to-end release pipeline
  repos                      browse / clone / create / release GitHub repos
  version                    show AutoSys version

Global flags:
  -y, --yes        accept defaults (non-interactive)
  -V, --version    show version and exit
  -h, --help       show help

OAuth note:
  The device-flow client ID defaults to GitHub CLI's public client id so the
  tool works out of the box. Before a production release, register your own
  GitHub OAuth app (GitHub > Settings > Developer settings > OAuth Apps) and
  set AUTOSYS_CLIENT_ID=<your id> (Windows: `setx AUTOSYS_CLIENT_ID ...`).
  `autosys login --client-id <id>` also works per-login.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

APP_NAME = "AutoSys"
VERSION = "2.0.2"
TAGLINE = "YOUR PROJECT'S COMMAND CENTER"

# GitHub OAuth (device flow). The default is GitHub CLI's public client id so
# the tool works out of the box for development. PRODUCTION BUILDS MUST set
# AUTOSYS_CLIENT_ID to your own OAuth app id (see module docstring).
GH_CLI_PUBLIC_ID = "178c6fc778ccc68e1d6a"
GH_CLIENT_ID = os.environ.get("AUTOSYS_CLIENT_ID", GH_CLI_PUBLIC_ID)
GH_SCOPE = "repo workflow read:org"
GH_API = os.environ.get("AUTOSYS_GH_API", "https://api.github.com")
GH_DEVICE_CODE = "https://github.com/login/device/code"
GH_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"

CONFIG_DIR = Path(os.environ.get("AUTOSYS_CONFIG_DIR", Path.home() / ".autosys"))
AUTH_FILE = CONFIG_DIR / "auth.json"

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", ".tox", "dist", "build",
    "__pycache__", ".idea", ".vscode", "target", "vendor", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".autosys", ".terraform", ".next",
    ".svelte-kit", "coverage", ".cache",
}
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "Gemfile.lock", "go.sum",
}
MAX_SCAN_FILE = 1024 * 1024
MAX_SCAN_FILES = 20000
MAX_LARGE_FILE = 10 * 1024 * 1024
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".lock", ".pdf", ".zip", ".gz", ".woff", ".woff2",
}

# Windows console: force UTF-8 output so rich's unicode glyphs render correctly
# (default cp1252 codepage crashes on ✓/→/⚠ and the box-drawing banner).
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

console = Console()
err_console = Console(stderr=True)


# --------------------------------------------------------------------------
# Banner / logo
# --------------------------------------------------------------------------

BANNER_LETTERS = {
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "U": ["██╗   ██╗", "██║   ██║", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
    "Y": ["██╗   ██╗", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚██╔╝  ", "   ██║   ", "   ╚═╝   "],
}


def banner_lines() -> str:
    rows = ["" for _ in range(6)]
    for ch in "AUTOSYS":
        letter = BANNER_LETTERS[ch]
        for i in range(6):
            rows[i] += letter[i] + " "
    return "\n".join(rows)


def print_banner() -> None:
    colors = ["cyan", "bright_cyan", "blue", "magenta", "bright_magenta", "cyan"]
    lines = banner_lines().splitlines()
    styled = Text()
    for i, line in enumerate(lines):
        styled.append(line, style=colors[i % len(colors)])
        if i < len(lines) - 1:
            styled.append("\n")
    console.print(
        Panel(
            styled,
            border_style="bright_cyan",
            subtitle=f"[bold cyan]v{VERSION}[/] — {TAGLINE}",
        )
    )


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _tty() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def ask(prompt: str, **kw):
    """Prompt.ask that degrades gracefully on EOF / non-tty (piped)."""
    if not _tty():
        return kw.get("default")
    try:
        return Prompt.ask(prompt, **kw)
    except EOFError:
        return kw.get("default")


def confirm(prompt: str, default: bool = False) -> bool:
    if not _tty():
        return default
    try:
        return Confirm.ask(prompt, default=default)
    except EOFError:
        return default


def ask_confirm(prompt: str, yes: bool, default: bool = False) -> bool:
    return True if yes else confirm(prompt, default=default)


def fail(msg: str, code: int = 1):
    err_console.print(f"[bold red]✗ {msg}[/]")
    sys.exit(code)


def ok(msg: str):
    console.print(f"[bold green]✓ {msg}[/]")


def warn(msg: str):
    console.print(f"[bold yellow]⚠ {msg}[/]")


def info(msg: str):
    console.print(f"[cyan]{msg}[/]")


def git(root: Path | None, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    cmd = ["git"]
    if root is not None:
        cmd += ["-C", str(root)]
    cmd += list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"git timed out after {timeout}s")


def is_git_repo(root: Path) -> bool:
    return git(root, "rev-parse", "--is-inside-work-tree").returncode == 0


def repo_root(start: Path | None = None) -> Path | None:
    start = start or Path.cwd()
    p = git(start, "rev-parse", "--show-toplevel")
    if p.returncode == 0:
        return Path(p.stdout.strip())
    return None


def current_branch(root: Path) -> str:
    p = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    return p.stdout.strip() or "HEAD"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def first_existing(root: Path, *names: str) -> Path | None:
    for n in names:
        p = root / n
        if p.exists():
            return p
    return None


# --------------------------------------------------------------------------
# Auth store (Windows DPAPI secure storage) + GitHub API
# --------------------------------------------------------------------------

class SecureStore:
    """Credential storage.

    Windows: the token is encrypted with DPAPI (CryptProtectData) so it is
    tied to the Windows user and cannot be read as plaintext from disk.
    Other OSes: falls back to a 0600-permission JSON file.
    """

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _dpapi_encrypt(data: bytes) -> bytes | None:
        try:
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD),
                            ("pbData", ctypes.POINTER(ctypes.c_byte))]
            buf = ctypes.create_string_buffer(data, len(data))
            in_b = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
            out_b = DATA_BLOB()
            if not ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(in_b), None, None, None, None, 0, ctypes.byref(out_b)
            ):
                return None
            raw = ctypes.string_at(out_b.pbData, out_b.cbData)
            ctypes.windll.kernel32.LocalFree(out_b.pbData)
            return bytes(raw)
        except Exception:
            return None

    @staticmethod
    def _dpapi_decrypt(blob: bytes) -> bytes | None:
        try:
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD),
                            ("pbData", ctypes.POINTER(ctypes.c_byte))]
            buf = ctypes.create_string_buffer(blob, len(blob))
            in_b = DATA_BLOB(len(blob), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
            out_b = DATA_BLOB()
            if not ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(in_b), None, None, None, None, 0, ctypes.byref(out_b)
            ):
                return None
            raw = ctypes.string_at(out_b.pbData, out_b.cbData)
            ctypes.windll.kernel32.LocalFree(out_b.pbData)
            return bytes(raw)
        except Exception:
            return None

    def save(self, payload: dict) -> str:
        """Returns the storage method actually used ('dpapi' or 'file')."""
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        blob = self._dpapi_encrypt(raw) if os.name == "nt" else None
        if blob is not None:
            self.path.write_bytes(b"DPAPI1" + blob)
            return "dpapi"
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return "file"

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            head = self.path.read_bytes()
        except OSError:
            return {}
        if head.startswith(b"DPAPI1"):
            raw = self._dpapi_decrypt(head[6:])
            if raw is None:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}
        try:
            return json.loads(head.decode("utf-8"))
        except Exception:
            return {}


auth_store = SecureStore(AUTH_FILE)


def load_auth() -> dict:
    return auth_store.load()


def save_auth(auth: dict) -> None:
    if auth.get("token"):
        auth_store.save(auth)
    else:
        auth_store.save({})


def has_auth() -> bool:
    return bool(load_auth().get("token"))


def get_client_id(cli_id: str | None = None) -> str:
    return (cli_id or os.environ.get("AUTOSYS_CLIENT_ID") or GH_CLIENT_ID or GH_CLI_PUBLIC_ID)


def warn_default_client_id(client_id: str) -> None:
    """Loud, friendly heads-up when running on GitHub CLI's public client id."""
    if client_id != GH_CLI_PUBLIC_ID:
        return
    console.print(
        Panel(
            "[yellow]You are using [bold]GitHub CLI's public OAuth client ID[/bold] "
            "(dev convenience). For production, register your own OAuth app:\n"
            "[cyan]GitHub → Settings → Developer settings → OAuth Apps → New OAuth app[/cyan]\n"
            "then set [bold]AUTOSYS_CLIENT_ID[/bold] (e.g. `setx AUTOSYS_CLIENT_ID <id>` on Windows)\n"
            "or run [bold]autosys login --client-id <your-id>[/bold].[/yellow]",
            title="[bold yellow]OAuth app not configured[/]",
            border_style="yellow",
        )
    )


class GitHubAPI:
    def __init__(self, token: str | None = None):
        self.token = token or load_auth().get("token")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": f"AutoSys/{VERSION}",
            }
        )
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def request(self, method: str, path: str, params=None, json_body=None, timeout: int = 20):
        url = path if path.startswith("http") else GH_API + path
        r = self.session.request(method, url, params=params, json=json_body, timeout=timeout)
        if r.status_code >= 400:
            msg = ""
            try:
                body = r.json()
                msg = body.get("message", "")
                if r.status_code == 403 and "rate limit" in msg.lower():
                    msg += " — API rate limit hit, wait a bit and retry."
            except Exception:
                pass
            raise RuntimeError(f"GitHub API {r.status_code}: {msg or r.text[:200]}")
        if r.status_code == 204:
            return None
        try:
            return r.json()
        except Exception:
            return r.text

    def get(self, path: str, params=None):
        return self.request("GET", path, params=params)

    def post(self, path: str, body=None):
        return self.request("POST", path, json_body=body)

    def patch(self, path: str, body=None):
        return self.request("PATCH", path, json_body=body)

    def user(self) -> dict:
        return self.get("/user")

    def list_repos(self, max_pages: int = 5) -> list[dict]:
        repos = []
        for page in range(1, max_pages + 1):
            batch = self.get("/user/repos", {"per_page": 100, "page": page, "sort": "updated"})
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
        return repos

    def releases(self, repo: str) -> list[dict]:
        return self.get(f"/repos/{repo}/releases", {"per_page": 50})

    def create_release(self, repo: str, tag_name: str, name: str | None = None,
                       body: str | None = None, draft: bool = False) -> dict:
        return self.post(
            f"/repos/{repo}/releases",
            {"tag_name": tag_name, "name": name or tag_name, "body": body or "", "draft": draft},
        )

    def create_repo(self, name: str, private: bool = False,
                    description: str = "", auto_init: bool = True) -> dict:
        return self.post(
            "/user/repos",
            {
                "name": name,
                "private": private,
                "description": description,
                "auto_init": auto_init,
            },
        )


REMOTE_RE = re.compile(
    r"(?:https?://[^/]+/|git@[^:]+:|ssh://[^/]+/)([^/]+)/([^/]+?)(?:\.git)?/?$"
)


def remote_repo(root: Path) -> tuple[str, str] | None:
    p = git(root, "config", "--get", "remote.origin.url")
    if p.returncode != 0:
        return None
    m = REMOTE_RE.match(p.stdout.strip())
    if m:
        return m.group(1), m.group(2)
    return None


def device_flow(client_id: str, scope: str, no_browser: bool = False) -> dict:
    """GitHub device-flow login. Returns {"token", "user"} or raises RuntimeError."""
    warn_default_client_id(client_id)
    r = requests.post(
        GH_DEVICE_CODE,
        data={"client_id": client_id, "scope": scope},
        headers={"Accept": "application/json"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"GitHub device-flow start failed ({r.status_code}): {r.text[:200]}")
    d = r.json()
    device_code = d.get("device_code")
    user_code = d.get("user_code")
    uri = d.get("verification_uri", "https://github.com/login/device")
    if not device_code or not user_code:
        raise RuntimeError(f"Unexpected device-flow response: {d}")

    console.print(
        Panel(
            Group(
                Text("\nEnter this code on GitHub:", style="bold"),
                Text(f"  {user_code}", style="bold white on blue"),
                Text("\nWaiting for authorization…", style="dim"),
            ),
            title=f"[bold]GitHub device authorization[/] — {client_id}",
            border_style="cyan",
        )
    )
    if not no_browser:
        try:
            webbrowser.open(f"{uri}?user_code={user_code}")
        except Exception:
            pass

    interval = max(5, int(d.get("interval", 5)))
    deadline = time.time() + int(d.get("expires_in", 900))
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}[/]"),
        console=console,
        transient=True,
    ) as prog:
        task = prog.add_task(f"Waiting for browser authorization ({user_code})…", total=None)
        while time.time() < deadline:
            time.sleep(interval)
            prog.update(task, description=f"Still waiting… code {user_code}")
            try:
                t = requests.post(
                    GH_OAUTH_TOKEN,
                    data={
                        "client_id": client_id,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Accept": "application/json"},
                    timeout=30,
                ).json()
            except requests.RequestException as e:
                raise RuntimeError(f"Network error during device flow: {e}")
            if t.get("access_token"):
                token = t["access_token"]
                api = GitHubAPI(token)
                user = api.user()
                return {"token": token, "user": user}
            err = t.get("error")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            friendly = {
                "access_denied": "Authorization denied in the browser.",
                "expired_token": "The code expired — please try again.",
                "unsupported_grant_type": "Unsupported grant type — update AutoSys.",
            }
            raise RuntimeError(friendly.get(err, err or str(t)))
    raise RuntimeError("Timed out waiting for authorization — please retry.")


# --------------------------------------------------------------------------
# Project memory (.autosys/)
# --------------------------------------------------------------------------

def project_dir(root: Path) -> Path:
    return root / ".autosys"


def project_memory(root: Path) -> dict:
    return load_json(project_dir(root) / "project.json")


def load_project_memory(root: Path | None = None) -> dict:
    root = root or repo_root()
    if not root:
        return {}
    return project_memory(root)


def save_project_memory(root: Path, data: dict) -> None:
    save_json(project_dir(root) / "project.json", data)


def cmd_init(yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — run `git init` first (or cd into a repo).")
    mem_path = project_dir(root) / "project.json"
    mem = load_json(mem_path)
    if mem:
        ok(f"Project memory already initialized for [bold]{mem.get('name', root.name)}[/]")
        return

    name = root.name if yes else ask("Project name", default=root.name)
    desc = "" if yes else (ask("Short description (optional)", default="") or "")
    branch = current_branch(root)
    style = "conventional" if yes else ask("Commit message style", choices=["conventional", "simple"], default="conventional")

    mem = {
        "name": name,
        "description": desc,
        "default_branch": branch,
        "commit_style": style,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_project_memory(root, mem)
    ok(f"Project memory saved to [bold]{mem_path}[/]")
    info("AutoSys will use this for smarter commit types, readiness checks and releases.")


# --------------------------------------------------------------------------
# Version detection / bumping
# --------------------------------------------------------------------------

SEMVER = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.\-]+)?")


def parse_semver(s: str) -> tuple[int, int, int] | None:
    m = SEMVER.search(s or "")
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def bump_semver(ver: tuple[int, int, int], kind: str) -> str:
    major, minor, patch = ver
    if kind == "major":
        major += 1
        minor = 0
        patch = 0
    elif kind == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def detect_version_files(root: Path) -> list[dict]:
    """All places a project version lives. Returns [{path, kind, version}]."""
    out: list[dict] = []

    def add(path: str, kind: str, version: str):
        if version:
            out.append({"path": path, "kind": kind, "version": version.strip()})

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*version\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
        if m:
            add("pyproject.toml", "pyproject", m.group(1))

    pkg = root / "package.json"
    if pkg.exists():
        try:
            add("package.json", "package.json", str(json.loads(pkg.read_text(encoding="utf-8")).get("version", "")))
        except Exception:
            pass

    cargo = root / "Cargo.toml"
    if cargo.exists():
        m = re.search(r"^\[package\][\s\S]*?^version\s*=\s*\"([^\"]+)\"",
                      cargo.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            add("Cargo.toml", "cargo", m.group(1))

    setup = root / "setup.py"
    if setup.exists():
        m = re.search(r"version\s*=\s*[\"']([^\"']+)[\"']",
                      setup.read_text(encoding="utf-8", errors="replace"))
        if m:
            add("setup.py", "setup.py", m.group(1))

    setup_cfg = root / "setup.cfg"
    if setup_cfg.exists():
        m = re.search(r"^version\s*=\s*([^\s]+)", setup_cfg.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            add("setup.cfg", "setup.cfg", m.group(1))

    for name in ("VERSION", "version.txt"):
        f = root / name
        if f.exists():
            add(name, "version-file", f.read_text(encoding="utf-8", errors="replace").strip())

    for py in root.rglob("__init__.py"):
        parts = set(py.relative_to(root).parts)
        if parts & SKIP_DIRS:
            continue
        m = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']",
                      py.read_text(encoding="utf-8", errors="replace"))
        if m:
            add(str(py.relative_to(root)).replace("\\", "/"), "__init__.py", m.group(1))
            break

    lock = root / "package-lock.json"
    if lock.exists():
        try:
            add("package-lock.json", "lock", str(json.loads(lock.read_text(encoding="utf-8")).get("version", "")))
        except Exception:
            pass

    return out


PRIMARY_ORDER = [
    "pyproject.toml", "package.json", "Cargo.toml", "setup.py", "setup.cfg",
    "__init__.py", "VERSION", "version.txt", "package-lock.json",
]


def primary_version(root: Path) -> str | None:
    by_path = {f["path"]: f["version"] for f in detect_version_files(root)}
    for p in PRIMARY_ORDER:
        if p in by_path:
            return by_path[p]
    return None


def latest_tag(root: Path) -> str | None:
    p = git(root, "tag", "--list", "--sort=-version:refname")
    if p.returncode != 0:
        return None
    found = []
    for t in p.stdout.splitlines():
        t = t.strip()
        parsed = parse_semver(t)
        if parsed:
            found.append((parsed, t))
    if not found:
        return None
    found.sort(key=lambda x: x[0], reverse=True)
    return found[0][1]


def readme_version(root: Path) -> str | None:
    readme = first_existing(root, "README.md", "README.rst", "README.txt", "README")
    if not readme:
        return None
    text = readme.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"v?(\d+)\.(\d+)\.(\d+)", text):
        major = int(m.group(1))
        if 0 <= major <= 99:
            return m.group(0)
    return None


def set_version(root: Path, entry: dict, new_version: str) -> None:
    """Rewrite the version inside a detected file."""
    path = root / entry["path"]
    text = path.read_text(encoding="utf-8", errors="replace")
    old = entry["version"]
    if entry["kind"] in ("package.json", "lock"):
        data = json.loads(text)
        data["version"] = new_version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif entry["kind"] == "pyproject":
        text = re.sub(r"(?m)^(\s*version\s*=\s*[\"'])[^\"']+([\"'])",
                      lambda m: m.group(1) + new_version + m.group(2), text, count=1)
        path.write_text(text, encoding="utf-8")
    elif entry["kind"] == "cargo":
        text = re.sub(r"^(\[package\][\s\S]*?^version\s*=\s*\")[^\"]+(\")",
                      lambda m: m.group(1) + new_version + m.group(2), text, count=1, flags=re.M)
        path.write_text(text, encoding="utf-8")
    elif entry["kind"] == "__init__.py":
        text = re.sub(r"(__version__\s*=\s*[\"'])[^\"']+([\"'])",
                      lambda m: m.group(1) + new_version + m.group(2), text, count=1)
        path.write_text(text, encoding="utf-8")
    elif entry["kind"] == "setup.py":
        text, n = re.subn(r"(?m)^(\s*version\s*=\s*[\"'])[^\"']+([\"'])",
                          lambda m: m.group(1) + new_version + m.group(2), text, count=1)
        if n == 0:  # fallback: inline `version="x"` (e.g. single-line setup(...))
            text = re.sub(r"(version\s*=\s*[\"'])[^\"']+([\"'])",
                          lambda m: m.group(1) + new_version + m.group(2), text, count=1)
        path.write_text(text, encoding="utf-8")
    elif entry["kind"] == "setup.cfg":
        text = re.sub(r"(?m)^(version\s*=\s*)[^\s]+",
                      lambda m: m.group(1) + new_version, text, count=1)
        path.write_text(text, encoding="utf-8")
    elif entry["kind"] == "version-file":
        path.write_text(new_version + "\n", encoding="utf-8")
    else:
        raise ValueError(f"Cannot auto-bump {entry['path']} (kind={entry['kind']}) — bump manually.")


# --------------------------------------------------------------------------
# Secrets engine
# --------------------------------------------------------------------------

SECRET_PATTERNS = [
    ("AWS Access Key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("AWS Secret Key", r"(?i)\b(aws|amazon)?_?(secret|access)_?key\b.{0,30}[A-Za-z0-9/+=]{40}"),
    ("GitHub PAT", r"\bghp_[A-Za-z0-9]{36}\b"),
    ("GitHub Fine-grained PAT", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    ("GitHub OAuth", r"\bgho_[A-Za-z0-9]{36}\b"),
    ("GitLab PAT", r"\bglpat-[A-Za-z0-9_\-]{20,}\b"),
    ("Slack Token", r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    ("Slack Webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
    ("Stripe Secret Key", r"\bsk_live_[0-9A-Za-z]{24,}\b"),
    ("Stripe Restricted", r"\brk_live_[0-9A-Za-z]{24,}\b"),
    ("OpenAI Key", r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"),
    ("Anthropic Key", r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    ("Google API Key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("Google OAuth Client Secret", r"\bGOCSPX-[0-9A-Za-z_\-]{20,}\b"),
    ("Twilio API Key", r"\bSK[0-9a-fA-F]{32}\b"),
    ("SendGrid Key", r"\bSG\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\b"),
    ("Mailgun Key", r"\bkey-[0-9a-fA-F]{32}\b"),
    ("Postgres URL", r"postgres(?:ql)?://[A-Za-z0-9_.\-]+:[^@\s]+@[^\s]+"),
    ("MySQL URL", r"mysql://[A-Za-z0-9_.\-]+:[^@\s]+@[^\s]+"),
    ("Mongo URL", r"mongodb(?:\+srv)?://[A-Za-z0-9_.\-]+:[^@\s]+@[^\s]+"),
    ("Redis URL", r"redis://[A-Za-z0-9_.\-]*:[^@\s]+@[^\s]+"),
    ("Heroku API Key", r"\b(?:heroku|HRKU)-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    ("Private Key Block", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ("JWT (HS256)", r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("Generic Bearer Token", r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{20,}\b"),
    (".env committed", r"(?i)\b(?:api[_-]?key|secret|password|token|auth)\b\s*=\s*['\"]?[^\s'\"(]{8,}(?!\w*\s*\()"),
]

SECRET_FILE_NAMES = {".env", ".env.prod", ".env.production", ".env.local",
                     "id_rsa", "id_dsa", "id_ecdsa", "credentials.json", "secrets.json"}


def scan_secrets(root: Path, quiet: bool = False) -> list[dict]:
    """Scan tracked-looking project files for leaked secrets (bounded)."""
    findings: list[dict] = []
    files_scanned = 0
    compiled = [(name, re.compile(pat)) for name, pat in SECRET_PATTERNS]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        parts = set(rel.parts)
        if parts & SKIP_DIRS or rel.name in SKIP_FILES:
            continue
        if ".git" in parts:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_FILE:
                continue
        except OSError:
            continue
        files_scanned += 1
        if files_scanned > MAX_SCAN_FILES:
            break
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, rx in compiled:
            for m in rx.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append({
                    "file": str(rel).replace("\\", "/"),
                    "line": line_no,
                    "kind": name,
                    "match": m.group(0)[:80],
                })
                if len(findings) >= 500:
                    return findings
    return findings


# --------------------------------------------------------------------------
# Git log / diff / stats helpers
# --------------------------------------------------------------------------

CONVENTIONAL_TYPES = {
    "feat": ("✨ New feature", "green"),
    "fix": ("🐛 Bug fix", "red"),
    "docs": ("📝 Documentation", "cyan"),
    "style": ("💅 Code style", "magenta"),
    "refactor": ("♻️ Refactor", "yellow"),
    "perf": ("⚡ Performance", "bright_red"),
    "test": ("🧪 Tests", "blue"),
    "build": ("📦 Build system", "bright_blue"),
    "ci": ("🔧 CI", "bright_cyan"),
    "chore": ("🧹 Chores", "white"),
    "revert": ("↩️ Revert", "red"),
    "security": ("🛡 Security", "bright_red"),
}

CONVENTIONAL_BUMPS = {
    "feat": "minor",
    "fix": "patch",
    "perf": "patch",
    "security": "patch",
    "refactor": "patch",
    "revert": "patch",
}

FEATURE_DIRS = {
    "algorithms": "Algorithms",
    "auth": "Auth",
    "backend": "Backend",
    "api": "API",
    "cli": "CLI",
    "cli/commands": "CLI commands",
    "config": "Config",
    "core": "Core",
    "data": "Data",
    "database": "Database",
    "db": "Database",
    "docs": "Docs",
    "frontend": "Frontend",
    "scripts": "Scripts",
    "src": "Source",
    "tests": "Tests",
    "test": "Tests",
    "utils": "Utils",
    "utils/helpers": "Utils",
    "web": "Web",
}

# https://conventionalcommits.org regex
CONVENTIONAL_RE = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|security)(\([^)]+\))?!?:\s.*")


def git_log(root: Path, limit: int = 100) -> list[dict]:
    """Parsed commit log: subject, author, date, files, insertions, deletions."""
    p = git(
        root, "log", f"-{limit}", "--pretty=format:%x1f%h%x1f%an%x1f%ae%x1f%ad%x1f%s",
        "--date=format:%Y-%m-%d %H:%M", "--numstat",
    )
    commits: list[dict] = []
    current: dict | None = None
    for line in (p.stdout or "").splitlines():
        if line.startswith("\x1f"):
            if current:
                commits.append(current)
            fields = line.strip("\x1f").split("\x1f")
            current = {
                "hash": fields[0] if len(fields) > 0 else "",
                "author": fields[1] if len(fields) > 1 else "",
                "email": fields[2] if len(fields) > 2 else "",
                "date": fields[3] if len(fields) > 3 else "",
                "subject": fields[4] if len(fields) > 4 else "",
                "insertions": 0,
                "deletions": 0,
                "files": [],
            }
        elif current is not None and line.strip():
            parts = line.split("\t")
            if len(parts) == 3:
                ins = parts[0]
                dele = parts[1]
                fname = parts[2]
                current["insertions"] += int(ins) if ins.isdigit() else 0
                current["deletions"] += int(dele) if dele.isdigit() else 0
                current["files"].append(fname)
    if current:
        commits.append(current)
    return commits


def dir_density(commits: list[dict]) -> list[tuple[str, int, str]]:
    """Map changed files to feature areas. Returns [(area, commits, sample)]."""
    counts: dict[str, int] = {}
    samples: dict[str, str] = {}
    for c in commits:
        seen = set()
        for f in c["files"]:
            parts = f.split("/")
            area = None
            for depth in range(len(parts), 0, -1):
                cand = "/".join(parts[:depth])
                if cand in FEATURE_DIRS:
                    area = FEATURE_DIRS[cand]
                    break
            if area is None:
                area = "Other"
            if area not in seen:
                counts[area] = counts.get(area, 0) + 1
                seen.add(area)
                samples.setdefault(area, c["hash"])
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)


def commits_between(root: Path, since_tag: str | None) -> list[dict]:
    if since_tag:
        p = git(root, "log", f"{since_tag}..HEAD", "--pretty=format:%x1f%h%x1f%an%x1f%ad%x1f%s",
                "--date=format:%Y-%m-%d", "--no-merges")
    else:
        p = git(root, "log", "-30", "--pretty=format:%x1f%h%x1f%an%x1f%ad%x1f%s",
                "--date=format:%Y-%m-%d", "--no-merges")
    commits = []
    for line in (p.stdout or "").splitlines():
        fields = line.strip("\x1f").split("\x1f")
        if len(fields) >= 4:
            commits.append({
                "hash": fields[0],
                "author": fields[1],
                "date": fields[2],
                "subject": fields[3],
            })
    return commits


# --------------------------------------------------------------------------
# Interactive pickers
# --------------------------------------------------------------------------

def pick_from(options: list[str], prompt_text: str = "Pick one:") -> str | None:
    """Arrow-key selector with type-ahead; degrades to a numbered prompt."""
    if len(options) == 0:
        return None
    if len(options) == 1:
        info(f"{prompt_text} → {options[0]}")
        return options[0]
    try:
        import readline  # noqa: F401  (probe tty usability)
        if not sys.stdin.isatty():
            raise EOFError
        print("\n" + prompt_text + "  (↑/↓ move, Enter select, type to filter)")
    except Exception:
        return ask(prompt_text, choices=options, default=options[0])
    selected = 0
    filtered = options
    buf = ""
    try:
        while True:
            for i, opt in enumerate(filtered):
                marker = "▸" if i == selected else " "
                style = "bold cyan" if i == selected else ""
                console.print(f" {marker} [{'bold cyan' if i == selected else 'dim'}]{opt}[/]")
            print(f"\n Filter: {buf}", end="\r")
            ch = _read_key()
            if ch in ("\r", "\n"):
                print("\n")
                return filtered[selected]
            if ch in ("\x1b[A", "k"):  # up
                selected = (selected - 1) % len(filtered)
                _clear_lines(len(filtered) + 1)
            elif ch in ("\x1b[B", "j"):  # down
                selected = (selected + 1) % len(filtered)
                _clear_lines(len(filtered) + 1)
            elif ch in ("\x03", "\x1b"):  # Ctrl-C / Esc
                print("\n")
                return None
            elif ch == "\x7f":  # backspace
                buf = buf[:-1]
                filtered = _filter_options(options, buf)
                selected = 0
                _clear_lines(len(filtered) + 1)
            elif ch.isprintable():
                buf += ch
                filtered = _filter_options(options, buf)
                selected = 0
                _clear_lines(len(filtered) + 1)
    except (EOFError, KeyboardInterrupt):
        return ask(prompt_text, choices=options, default=options[0])


def _filter_options(options: list[str], buf: str) -> list[str]:
    return [o for o in options if buf.lower() in o.lower()] or options


def _clear_lines(n: int) -> None:
    for _ in range(n):
        print("\x1b[1A\x1b[2K", end="")
    print("\r", end="")


def _read_key() -> str:
    if sys.platform == "win32":
        import msvcrt
        first = msvcrt.getwch()
        if first in ("\x00", "\xe0"):  # arrow keys
            second = msvcrt.getwch()
            return {"H": "\x1b[A", "P": "\x1b[B"}.get(second, second)
        return first
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            rest = sys.stdin.read(2)
            return ch + rest
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def ask_optional(prompt_text: str, default: str = "") -> str:
    """Optional free-text input that returns '' when empty (skips prompts)."""
    return str(ask(prompt_text, default=default) or "").strip()


# --------------------------------------------------------------------------
# Git status / diff / log helpers
# --------------------------------------------------------------------------

def working_changes(root: Path) -> int:
    p = git(root, "status", "--porcelain")
    return len([l for l in p.stdout.splitlines() if l.strip()])


def unstaged_files(root: Path) -> list[str]:
    """Files with working-tree changes (modified/deleted but NOT staged)."""
    p = git(root, "diff", "--name-only")
    return [l for l in p.stdout.splitlines() if l.strip()]


def untracked_files(root: Path) -> list[str]:
    p = git(root, "ls-files", "--others", "--exclude-standard")
    return [l for l in p.stdout.splitlines() if l.strip()]


def _is_tracked(root: Path, rel: str) -> bool:
    return git(root, "ls-files", "--error-unmatch", "--", rel).returncode == 0


def _gitignored(root: Path, rel: str) -> bool:
    return git(root, "check-ignore", "-q", "--", rel).returncode == 0


# --------------------------------------------------------------------------
# Ship readiness check (`status`)
# --------------------------------------------------------------------------

def _iter_repo_files(root: Path, cap: int = MAX_SCAN_FILES) -> Iterator[Path]:
    """Yield project files: single bounded walk that skips .git and SKIP_DIRS."""
    n = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if ".git" in rel.parts or set(rel.parts) & SKIP_DIRS:
            continue
        yield path
        n += 1
        if n >= cap:
            break


def run_check(root: Path, no_remote: bool = False) -> int:
    """Ship-readiness report — 5 categories x 20 pts = 100, with a full breakdown."""
    console.print(Panel(f"[bold cyan]Ship-readiness report[/] — [bold]{root}[/]", box=box.ROUNDED))
    branch = current_branch(root)
    repo = remote_repo(root)
    has_remote = repo is not None

    def chk(name, earned, max_pts, detail="", fix=""):
        return {"name": name, "earned": earned, "max": max_pts, "detail": detail, "fix": fix}

    categories = {}
    CAT = 20

    # ---------- Git (20) ----------
    git_checks = []
    if is_git_repo(root):
        git_checks.append(chk("Repo initialized", 5, 5, "git repo found"))
    else:
        git_checks.append(chk("Repo initialized", 0, 5, "not a git repo", "Run `git init`"))
    uname = git(root, "config", "user.name").stdout.strip()
    uemail = git(root, "config", "user.email").stdout.strip()
    if uname and uemail:
        git_checks.append(chk("Git identity set", 5, 5, f"{uname} <{uemail}>"))
    else:
        git_checks.append(chk("Git identity set", 0, 5, "user.name/user.email not set",
                              "git config user.name 'You' && git config user.email 'you@x.com'"))
    dirty = working_changes(root)
    if dirty == 0:
        git_checks.append(chk("Working tree clean", 5, 5, "no pending changes"))
    else:
        git_checks.append(chk("Working tree clean", 0, 5, f"{dirty} pending change(s)",
                              "Commit or stash first (`autosys commit`)"))
    if not has_remote:
        git_checks.append(chk("In sync with origin", 5, 5, "n/a — no remote configured"))
    else:
        rs = git(root, "rev-list", "--left-right", "--count", f"{branch}...origin/{branch}")
        if rs.returncode == 0:
            ahead, behind = rs.stdout.split()
            if int(ahead) == 0 and int(behind) == 0:
                git_checks.append(chk("In sync with origin", 5, 5, f"{branch} == origin/{branch}"))
            else:
                git_checks.append(chk("In sync with origin", 0, 5,
                                      f"{branch} is {ahead} ahead, {behind} behind origin/{branch}",
                                      "git push" if int(ahead) else "git pull"))
        else:
            git_checks.append(chk("In sync with origin", 5, 5, "n/a — origin/{branch} not fetched"))
    categories["Git"] = git_checks

    # ---------- Security (20) ----------
    sec_checks = []
    secrets = scan_secrets(root, quiet=True)
    if not secrets:
        sec_checks.append(chk("No leaked secrets", 10, 10, "scan clean"))
    else:
        names = sorted({s.get("file", "?") for s in secrets})
        sec_checks.append(chk("No leaked secrets", 0, 10,
                              f"{len(secrets)} potential secret(s): {', '.join(names[:3])}"
                              + ("..." if len(names) > 3 else ""),
                              "Run `autosys secrets` and remove them before pushing"))
    env_path = root / ".env"
    if not env_path.exists():
        sec_checks.append(chk(".env not tracked", 5, 5, "no .env file (nothing to leak)"))
    elif _is_tracked(root, ".env"):
        sec_checks.append(chk(".env not tracked", 0, 5, ".env is TRACKED in git",
                              "git rm --cached .env, then add `.env` to .gitignore"))
    elif not _gitignored(root, ".env"):
        sec_checks.append(chk(".env not tracked", 0, 5, ".env exists but is NOT gitignored",
                              "Add `.env` to .gitignore"))
    else:
        sec_checks.append(chk(".env not tracked", 5, 5, ".env is gitignored"))
    tracked_secrets = [f for f in sorted(SECRET_FILE_NAMES) if (root / f).exists() and _is_tracked(root, f)]
    unignored_secrets = [f for f in sorted(SECRET_FILE_NAMES) if (root / f).exists() and not _gitignored(root, f)]
    if tracked_secrets:
        sec_checks.append(chk("Secret files protected", 0, 5,
                              "tracked: " + ", ".join(tracked_secrets),
                              "git rm --cached " + " ".join(tracked_secrets)))
    elif unignored_secrets:
        sec_checks.append(chk("Secret files protected", 0, 5,
                              "not gitignored: " + ", ".join(unignored_secrets),
                              "Add them to .gitignore"))
    else:
        sec_checks.append(chk("Secret files protected", 5, 5, "no tracked/unignored secret files"))
    categories["Security"] = sec_checks

    # ---------- Version (20) ----------
    ver_checks = []
    vfiles = detect_version_files(root)
    if vfiles:
        ver_checks.append(chk("Version files present", 5, 5,
                              f"{len(vfiles)} file(s): " + ", ".join(f["path"] for f in vfiles[:4])
                              + ("..." if len(vfiles) > 4 else "")))
    else:
        ver_checks.append(chk("Version files present", 0, 5, "no version file found",
                              "Add package.json / pyproject.toml / VERSION"))
    if vfiles:
        versions = {f["path"]: f["version"] for f in vfiles}
        if len(set(versions.values())) == 1:
            ver_checks.append(chk("Version files consistent", 10, 10,
                                  f"all {len(vfiles)} file(s) at {list(versions.values())[0]}"))
        else:
            drift = ", ".join(f"{k}={v}" for k, v in versions.items())
            ver_checks.append(chk("Version files consistent", 0, 10, "drift: " + drift,
                                  "Run `autosys drift --fix`"))
    else:
        ver_checks.append(chk("Version files consistent", 0, 10, "n/a — no version files"))
    pv = primary_version(root)
    lt = latest_tag(root)
    if pv is None:
        ver_checks.append(chk("Version ahead of last tag", 5, 5, "n/a — no version detected"))
    elif lt is None:
        ver_checks.append(chk("Version ahead of last tag", 5, 5, f"n/a — no tags yet (v{pv})"))
    else:
        try:
            if parse_semver(pv) > parse_semver(lt):
                ver_checks.append(chk("Version ahead of last tag", 5, 5, f"{pv} > {lt}"))
            else:
                ver_checks.append(chk("Version ahead of last tag", 0, 5,
                                      f"{pv} is not ahead of {lt}",
                                      "Run `autosys finish` to bump + tag a release"))
        except TypeError:
            ver_checks.append(chk("Version ahead of last tag", 5, 5, f"n/a — unparseable ({pv}/{lt})"))
    categories["Version"] = ver_checks

    # ---------- Tests (20) ----------
    test_checks = []
    test_cmd = None
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tox.ini").exists():
        test_cmd = [sys.executable, "-m", "pytest", "-q"]
        framework = "pytest"
    elif (root / "package.json").exists():
        try:
            scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts", {})
            if scripts.get("test"):
                test_cmd = ["npm", "test", "--silent"]
                framework = "npm test"
            else:
                framework = None
        except Exception:
            framework = None
    elif (root / "Makefile").exists():
        test_cmd = ["make", "test"]
        framework = "make test"
    else:
        framework = None
    if test_cmd:
        test_checks.append(chk("Test framework detected", 5, 5, f"{framework} ({' '.join(test_cmd)})"))
    else:
        test_checks.append(chk("Test framework detected", 0, 5, "no pytest / test script / Makefile",
                               "Add a test command (e.g. `pytest` in pyproject.toml)"))
    n_test_files = 0
    for p in _iter_repo_files(root):
        n = p.name
        rel = str(p.relative_to(root)).replace("\\", "/")
        if n.startswith("test_") or n.endswith(("_test.py", ".test.js", ".test.ts")) or "/tests/" in f"/{rel}/":
            n_test_files += 1
    if n_test_files:
        test_checks.append(chk("Test files present", 5, 5, f"{n_test_files} test file(s) found"))
    else:
        test_checks.append(chk("Test files present", 0, 5, "no test files found",
                               "Add tests (test_*.py / *.test.js / tests/)"))
    if not test_cmd:
        if n_test_files:
            test_checks.append(chk("Tests pass", 0, 10, "test files present but no runner configured",
                                   "Add pytest or a `test` script"))
        else:
            test_checks.append(chk("Tests pass", 10, 10, "n/a — no tests to run"))
    else:
        run_cmd = (["cmd", "/c"] if os.name == "nt" and test_cmd[0] in ("npm", "npx") else []) + test_cmd
        info(f"Running tests: {' '.join(run_cmd)}")
        try:
            p = subprocess.run(run_cmd, cwd=str(root), capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            test_checks.append(chk("Tests pass", 0, 10, "timed out after 180s", "Run tests manually"))
        except FileNotFoundError:
            test_checks.append(chk("Tests pass", 0, 10, f"runner not found: {test_cmd[0]}",
                                   "Install the test runner (e.g. npm install)"))
        else:
            if p.returncode == 0:
                test_checks.append(chk("Tests pass", 10, 10, "exit 0"))
            else:
                tail = (p.stdout or p.stderr or "").strip().splitlines()
                detail = tail[-1][:90] if tail else f"exit code {p.returncode}"
                test_checks.append(chk("Tests pass", 0, 10, detail,
                                       "Fix failing tests, then rerun `autosys status`"))
    categories["Tests"] = test_checks

    # ---------- Docs (20) ----------
    doc_checks = []
    if first_existing(root, "README.md", "README.rst", "README.txt", "README"):
        doc_checks.append(chk("README", 8, 8, "found"))
    else:
        doc_checks.append(chk("README", 0, 8, "missing", "Add a README.md"))
    if first_existing(root, "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        doc_checks.append(chk("LICENSE", 6, 6, "found"))
    else:
        doc_checks.append(chk("LICENSE", 0, 6, "missing", "Add a LICENSE before publishing"))
    if first_existing(root, "CHANGELOG.md", "CHANGELOG", "HISTORY.md"):
        doc_checks.append(chk("CHANGELOG", 6, 6, "found"))
    else:
        doc_checks.append(chk("CHANGELOG", 0, 6, "missing", "Run `autosys finish` to generate one"))
    categories["Docs"] = doc_checks

    # ---------- score ----------
    cat_scores = {cat: sum(c["earned"] for c in checks) for cat, checks in categories.items()}
    total = sum(cat_scores.values())
    if total >= 90:
        grade, gcolor = "A", "green"
    elif total >= 75:
        grade, gcolor = "B", "cyan"
    elif total >= 60:
        grade, gcolor = "C", "yellow"
    elif total >= 40:
        grade, gcolor = "D", "magenta"
    else:
        grade, gcolor = "F", "red"

    console.print(f"\n[bold {gcolor}]Score: {total}/100[/]  —  Grade [bold {gcolor}]{grade}[/]\n")
    for cat in ("Git", "Security", "Version", "Tests", "Docs"):
        earned = cat_scores[cat]
        icon = chr(0x2713) if earned == CAT else (chr(0x2717) if earned == 0 else chr(0x26A0))
        icon_color = "green" if earned == CAT else ("red" if earned == 0 else "yellow")
        console.print(f"  [{icon_color}]{icon}[/] [bold]{cat:<10}[/] {earned:>2}/20")

    table = Table(title=f"[bold]Category breakdown[/] — {total}/100", box=box.SIMPLE_HEAVY, expand=False)
    table.add_column("Category", style="bold")
    table.add_column("Check", style="bold")
    table.add_column("Pts", justify="center")
    table.add_column("Result", justify="center", width=8)
    table.add_column("Detail / Fix")
    for cat in ("Git", "Security", "Version", "Tests", "Docs"):
        for c in categories[cat]:
            status_txt = "[green]PASS[/]" if c["earned"] == c["max"] else (
                "[yellow]PARTIAL[/]" if c["earned"] else "[red]FAIL[/]")
            pts_txt = f"{c['earned']}/{c['max']}"
            detail = c["detail"] or c["fix"]
            if c["earned"] < c["max"] and c["fix"]:
                detail = (f"{c['detail']}  →  [yellow]{c['fix']}[/]" if c["detail"]
                          else f"[yellow]{c['fix']}[/]")
            table.add_row(cat, c["name"], pts_txt, status_txt, detail)
    console.print(table)

    verdict = "SHIP IT" if grade in ("A", "B") else "FIX BEFORE SHIPPING"
    console.print(Panel(f"[bold {gcolor}]{verdict}[/]", box=box.ROUNDED))
    return 0 if grade in ("A", "B") else 1


def cmd_status(_yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    code = run_check(root)
    sys.exit(code)


# --------------------------------------------------------------------------
# Secrets command
# --------------------------------------------------------------------------

def cmd_secrets(_yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    console.print(f"[cyan]Scanning [bold]{root}[/] for leaked secrets…[/]")
    findings = scan_secrets(root)
    if not findings:
        ok("No secrets found — clean!")
        return
    table = Table(title=f"[bold red]{len(findings)} potential secret(s) found[/]", box=box.SIMPLE_HEAVY)
    table.add_column("File", style="bold")
    table.add_column("Line")
    table.add_column("Type", style="yellow")
    table.add_column("Match (truncated)")
    for f in findings[:50]:
        table.add_row(f["file"], str(f["line"]), f["kind"], f["match"])
    console.print(table)
    if len(findings) > 50:
        info(f"… and {len(findings) - 50} more. Run `autosys secrets` and pipe to a file for the full list.")
    if any(Path(f["file"]).name in SECRET_FILE_NAMES for f in findings):
        warn("You have secret files (.env etc.) present — check they are gitignored, not tracked.")
    if any(f["kind"] == "Private Key Block" for f in findings):
        warn("Private keys should NEVER be committed. Rotate them if they were ever pushed.")
    sys.exit(1)


# --------------------------------------------------------------------------
# Drift command
# --------------------------------------------------------------------------

def cmd_drift(yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    vfiles = detect_version_files(root)
    if not vfiles:
        info("No version files detected (package.json, pyproject.toml, VERSION…).")
        return
    versions = {f["path"]: f["version"] for f in vfiles}
    tag = latest_tag(root)
    readme_ver = readme_version(root)
    # compare versions semantically: "v1.2.3" and "1.2.3" are the same
    def _norm(v: str) -> str:
        return v[1:] if v.startswith("v") else v
    table = Table(title="Version drift", box=box.SIMPLE_HEAVY)
    table.add_column("Source", style="bold")
    table.add_column("Version")
    table.add_column("Note", style="dim")
    for f in vfiles:
        table.add_row(f["path"], f["version"], f["kind"])
    if tag:
        table.add_row("git tag (latest)", tag, "semver tag")
    if readme_ver:
        table.add_row("README", readme_ver, "first semver-looking string")
    console.print(table)
    unique = set(versions.values()) | ({tag} if tag else set())
    if len(set(_norm(v) for v in unique)) == 1:
        ok("All versions aligned.")
        return
    warn("Version drift detected — sources disagree:")
    for v in sorted(unique):
        files = [k for k, val in versions.items() if _norm(val) == _norm(v)]
        info(f"  {v}: {', '.join(files) if files else 'git tag / README'}")
    if yes or confirm("Align all versions to one value?", default=True):
        primary = versions.get("package.json") or versions.get("pyproject.toml") or tag or sorted(unique)[0]
        target = _norm(primary if yes else ask("Which version should everything be?", default=primary))
        if not target:
            warn("No target version — aborting.")
            return
        for f in vfiles:
            if _norm(f["version"]) != target:
                set_version(root, f, target)
                ok(f"  {f['path']} → {target}")
        if tag:
            info("Note: existing git tag untouched — retag with `git tag -f <tag> <sha>` if needed.")


# --------------------------------------------------------------------------
# Explain command (history as a story)
# --------------------------------------------------------------------------

def cmd_explain(args: list[str]) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    file_arg = args[0] if args else None
    if file_arg:
        p = git(root, "log", "--pretty=format:%x1f%h%x1f%an%x1f%ad%x1f%s",
                "--date=format:%Y-%m-%d", "--", file_arg)
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        if not lines:
            info(f"No history for [bold]{file_arg}[/] — file may be untracked.")
            return
        commits = []
        for line in lines:
            f = line.strip("\x1f").split("\x1f")
            if len(f) >= 4:
                commits.append({"hash": f[0], "author": f[1], "date": f[2], "subject": f[3]})
        console.print(Panel(f"[bold cyan]The story of [bold]{file_arg}[/][/]", box=box.ROUNDED))
        for c in commits:
            console.print(f"  [bold green]{c['hash']}[/] [dim]{c['date']}[/] — {c['subject']} [dim]({c['author']})[/]")
        info(f"\n{len(commits)} commit(s) touched this file.")
        return

    commits = git_log(root, 200)
    if not commits:
        info("No commits yet — tell your first story with `autosys commit`.")
        return
    authors: dict[str, int] = {}
    for c in commits:
        authors[c["author"]] = authors.get(c["author"], 0) + 1
    total_ins = sum(c["insertions"] for c in commits)
    total_del = sum(c["deletions"] for c in commits)
    areas = dir_density(commits)
    styled_types = []
    for c in commits:
        m = CONVENTIONAL_RE.match(c["subject"])
        if m:
            t = m.group(1)
            label, color = CONVENTIONAL_TYPES.get(t, (t, "white"))
            styled_types.append((t, label))
    type_counts: dict[str, int] = {}
    for t, _label in styled_types:
        type_counts[t] = type_counts.get(t, 0) + 1

    console.print(Panel(f"[bold cyan]Your project's story[/] — last {len(commits)} commits", box=box.ROUNDED))
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Commits analyzed", str(len(commits)))
    table.add_row("Active contributors", str(len(authors)))
    table.add_row("Lines added", f"+{total_ins:,}")
    table.add_row("Lines removed", f"-{total_del:,}")
    console.print(table)

    author_table = Table(title="Who did what", box=box.SIMPLE_HEAVY)
    author_table.add_column("Author")
    author_table.add_column("Commits", justify="right")
    author_table.add_column("Share", justify="right")
    top_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:8]
    for name, count in top_authors:
        share = f"{100 * count / len(commits):.0f}%"
        author_table.add_row(name, str(count), share)
    console.print(author_table)

    area_table = Table(title="Where the work landed", box=box.SIMPLE_HEAVY)
    area_table.add_column("Area", style="bold")
    area_table.add_column("Commits", justify="right")
    for area, count in areas[:8]:
        area_table.add_row(area, str(count))
    console.print(area_table)

    if type_counts:
        type_table = Table(title="Commit mix (conventional)", box=box.SIMPLE_HEAVY)
        type_table.add_column("Type")
        type_table.add_column("Count", justify="right")
        for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            label, color = CONVENTIONAL_TYPES.get(t, (t, "white"))
            type_table.add_row(f"[{color}]{label}[/]", str(count))
        console.print(type_table)


# --------------------------------------------------------------------------
# Doctor command
# --------------------------------------------------------------------------

def cmd_doctor(yes: bool = False) -> None:
    root = repo_root()
    console.print(Panel("[bold cyan]AutoSys doctor[/] — full diagnosis", box=box.ROUNDED))
    issues: list[str] = []

    if not root:
        issues.append("Not inside a git repository — run `git init` or cd into a project.")
        warn("✗ git repository")
    else:
        ok("Git repository detected")

    gitv = git(None, "--version").stdout.strip()
    info(f"git: {gitv}")

    if root:
        name = git(root, "config", "user.name").stdout.strip()
        email = git(root, "config", "user.email").stdout.strip()
        if name and email:
            ok(f"Git identity: {name} <{email}>")
        else:
            warn("Git identity not set — `git config user.name` / `user.email`")
            issues.append("git identity missing")

        branch = current_branch(root)
        mem = load_project_memory(root)
        if mem:
            ok(f"Project memory: {mem.get('name')} (style: {mem.get('commit_style')})")
        else:
            warn("No project memory — run `autosys init`")
            issues.append("project memory missing")

        repo = remote_repo(root)
        if repo:
            ok(f"Remote: {repo[0]}/{repo[1]}")
        else:
            warn("No origin remote configured")
            issues.append("no origin remote")

    if has_auth():
        auth = load_auth()
        user = auth.get("user", {})
        uname = user.get("login", "unknown") if isinstance(user, dict) else "unknown"
        ok(f"GitHub auth: logged in as {uname}")
    else:
        warn("Not logged in to GitHub — `autosys login` for remote features")
        issues.append("github auth missing")

    client_id = get_client_id()
    if client_id == GH_CLI_PUBLIC_ID:
        warn("Using GitHub CLI's public OAuth client ID — set AUTOSYS_CLIENT_ID for production")
        issues.append("oauth client id is default")
    else:
        ok(f"OAuth client ID configured: {client_id[:8]}…")

    # Python env
    py = sys.version.split()[0]
    info(f"python: {py}")
    try:
        import rich as _rich, requests as _requests  # noqa
        ok("rich + requests importable")
    except Exception as e:
        warn(f"Missing dependency: {e}")
        issues.append("missing dependency")

    # storage
    try:
        method = auth_store.path.parent.exists()
        _ = method
        if AUTH_FILE.exists():
            info(f"auth storage: {AUTH_FILE}")
        else:
            info("auth storage: not created yet")
    except Exception:
        pass

    if issues:
        console.print(Panel(
            "\n".join(f"  [yellow]→ {i}[/]" for i in issues),
            title="[bold yellow]Action items[/]",
            border_style="yellow",
        ))
    else:
        ok("All systems green — happy shipping!")


# --------------------------------------------------------------------------
# Changelog generator
# --------------------------------------------------------------------------

def build_changelog(root: Path, since_tag: str | None) -> str:
    commits = commits_between(root, since_tag)
    if not commits:
        return "No commits in range."
    lines: list[str] = []
    sections: dict[str, list[str]] = {}
    repo = remote_repo(root)
    url_base = f"https://github.com/{repo[0]}/{repo[1]}/commit/" if repo else ""
    for c in commits:
        m = CONVENTIONAL_RE.match(c["subject"])
        if m:
            kind = m.group(1)
            scope = m.group(2)[1:-1] if m.group(2) else ""
            breaking = "!" in m.group(0).split(":")[0]
            desc = c["subject"].split(":", 1)[1].strip()
            entry = f"- **{kind}**"
            if scope:
                entry += f" (`{scope}`)"
            if breaking:
                entry += " 🚨 BREAKING"
            entry += f": {desc} ([{c['hash']}]({url_base}{c['hash']}))"
            sections.setdefault(kind, []).append(entry)
        else:
            sections.setdefault("other", []).append(f"- {c['subject']} ([{c['hash']}]({url_base}{c['hash']}))")
    for kind in ("feat", "fix", "perf", "security", "refactor", "docs", "chore", "other"):
        if kind in sections:
            label, _c = CONVENTIONAL_TYPES.get(kind, (kind.title(), "white"))
            lines.append(f"### {label}\n")
            lines.extend(sections[kind])
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_changelog(root: Path, content: str) -> None:
    path = root / "CHANGELOG.md"
    header = "# Changelog\n\nAll notable changes to this project.\n\n"
    body = content.rstrip() + "\n" if content.strip() else "No changes yet.\n"
    existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    if not existing.strip():
        path.write_text(header + body, encoding="utf-8")
        return
    if header in existing:
        # Insert new entries right under the header, keeping the rest intact.
        new_existing = existing.replace(header, header + body, 1)
    else:
        # Preserve pre-existing content (e.g. custom intro) below the new entries.
        sep = "" if existing.endswith("\n") else "\n"
        new_existing = header + body + sep + existing
    path.write_text(new_existing, encoding="utf-8")


# --------------------------------------------------------------------------
# Commit wizard
# --------------------------------------------------------------------------

def stage_selected(root: Path, paths: list[str]) -> bool:
    """Stage a set of working-tree files (staging selected tracked files too)."""
    if not paths:
        return False
    args = ["add", "--"] + paths
    p = git(root, *args)
    if p.returncode != 0:
        err_console.print(f"[bold red]Failed to stage: {p.stderr.strip()}[/]")
        return False
    return True


def _suggest_type_from_files(paths: list[str]) -> str:
    for p in paths:
        low = p.lower()
        if any(t in low for t in ("test", "spec")):
            return "test"
        if low.startswith(("docs/", "readme", "changelog")):
            return "docs"
        if any(t in low for t in ("conf", "config", "docker", "workflow", ".github")):
            return "ci" if ".github" in low or "workflow" in low else "chore"
        if low.endswith((".lock", "poetry.lock", "package-lock.json")):
            return "chore"
    return "feat"


def _suggest_scope(paths: list[str]) -> str:
    for p in paths:
        parts = p.split("/")
        if len(parts) > 1 and parts[0] in ("src", "lib", "app", "tests", "docs", "config", "scripts", "cli"):
            return parts[0]
    return ""


def cmd_commit(yes: bool = False, push: bool | None = None, tag_ver: str | None = None) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    mem = load_project_memory(root)

    untracked = untracked_files(root)
    modified = unstaged_files(root)
    staged = git(root, "diff", "--name-only", "--cached").stdout.splitlines()
    candidates = sorted(set(untracked + modified + staged))
    if not candidates:
        info("Nothing to commit — working tree is clean.")
        return

    console.print(Panel(f"[bold cyan]Commit wizard[/] — [bold]{mem.get('name', root.name)}[/]", box=box.ROUNDED))
    if len(candidates) > 1 and not yes:
        selected = pick_from(candidates, "Select a file to stage (↑/↓ move, Enter pick):")
        if selected is None:
            warn("Aborted.")
            return
        paths = [selected]
    else:
        paths = candidates
    stage_selected(root, paths)

    staged_now = git(root, "diff", "--name-only", "--cached").stdout.splitlines()
    if not staged_now:
        warn("Nothing staged after selection.")
        return

    # default message
    if mem.get("commit_style") == "conventional":
        default_type = _suggest_type_from_files(paths)
        scope = _suggest_scope(paths)
        m = CONVENTIONAL_RE.match(git(root, "log", "-1", "--pretty=%s").stdout.strip())
        prev_type = m.group(1) if m else "feat"
        type_list = [t for t in CONVENTIONAL_TYPES if t != prev_type]
        type_list.insert(0, prev_type)
        if not yes:
            picked = pick_from(type_list, "Commit type:")
            if picked is None:
                warn("Aborted.")
                return
            ctype = picked
        else:
            ctype = default_type
        scope_str = ""
        if scope and not yes:
            scope_str = ask_optional(f"Scope (e.g. {scope}):", default=scope)
        breaking = False
        if ctype in ("feat", "fix") and not yes:
            breaking = confirm("Breaking change?", default=False)
        desc = ask("Description (short, imperative)", default="update") if not yes else "update"
        msg = f"{ctype}({scope_str})" if scope_str else ctype
        msg += "!" if breaking else ""
        msg += f": {desc}"
    else:
        msg = ask("Commit message", default="update") if not yes else "update"

    p = git(root, "commit", "-m", msg)
    if p.returncode != 0:
        err_console.print(f"[bold red]Commit failed:[/] {p.stderr.strip()}")
        err_console.print("[yellow]Fix the issue (often a pre-commit hook) and rerun `autosys commit`.[/]")
        sys.exit(1)
    ok(f"Committed: [bold]{msg}[/]")

    # optional push
    if push is None and not yes:
        push = confirm("Push to origin?", default=False)
    if push:
        p = git(root, "push")
        if p.returncode != 0:
            err_console.print(f"[bold red]Push failed:[/] {p.stderr.strip()}")
            err_console.print("[yellow]Run `git push` manually after resolving.[/]")
            sys.exit(1)
        ok("Pushed to origin.")

    # optional tag
    if tag_ver or (not yes and confirm("Create a version tag?", default=False)):
        tag = tag_ver or ask("Tag name (e.g. v1.2.3)", default="v0.1.0")
        if tag:
            p = git(root, "tag", tag)
            if p.returncode != 0:
                err_console.print(f"[bold red]Tag failed:[/] {p.stderr.strip()}")
            else:
                ok(f"Tagged [bold]{tag}[/]")


# --------------------------------------------------------------------------
# Checkpoint / restore
# --------------------------------------------------------------------------

def _checkpoint_index(root: Path) -> Path:
    return project_dir(root) / "checkpoints.json"


def _load_checkpoints(root: Path) -> list[dict]:
    return load_json(_checkpoint_index(root)).get("checkpoints", [])


def _save_checkpoints(root: Path, cps: list[dict]) -> None:
    save_json(_checkpoint_index(root), {"checkpoints": cps})


def cmd_checkpoint(yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    dirty = working_changes(root) > 0
    if dirty and not ask_confirm("Working tree has changes — snapshot them too? (recommended)", yes, default=True):
        warn("Aborted — stash/commit first if you want a clean snapshot.")
        return
    label = ask("Checkpoint label", default=f"checkpoint {datetime.now().strftime('%H:%M')}") if not yes else f"checkpoint {datetime.now().strftime('%H:%M')}"
    cps = _load_checkpoints(root)
    if len(cps) >= 20:
        warn("Checkpoint budget reached — dropping the oldest snapshot.")
        cps = cps[-19:]
    cp = {"label": label, "created": datetime.now().isoformat(timespec="seconds"), "sha": "pending"}
    cps = cps + [cp]
    _save_checkpoints(root, cps)
    console.print(f"[cyan]Saving checkpoint [bold]{label}[/]…[/]")
    ref = f"refs/autosys/checkpoint-{int(time.time())}"
    r1 = git(root, "add", "-A")
    if r1.returncode != 0:
        fail(f"Failed to stage snapshot: {r1.stderr.strip()}")
    git(root, "reset", "-q", "--", str(_checkpoint_index(root).relative_to(root)))
    tree = git(root, "write-tree")
    if tree.returncode != 0 or not tree.stdout.strip():
        fail(f"Failed to capture index tree: {tree.stderr.strip()}")
    r2 = git(root, "commit-tree", tree.stdout.strip(), "-p", "HEAD", "-m", f"autosys checkpoint: {label}")
    if r2.returncode != 0 or not r2.stdout.strip():
        fail("Failed to create snapshot commit.")
    sha = r2.stdout.strip()
    r3 = git(root, "update-ref", ref, sha)
    if r3.returncode != 0:
        fail(f"Failed to record snapshot: {r3.stderr.strip()}")
    cps[-1]["sha"] = sha
    cps[-1]["ref"] = ref
    _save_checkpoints(root, cps)
    ok(f"Checkpoint saved [bold]{sha[:10]}[/] — {label}")
    if dirty:
        git(root, "reset")
        info("Working tree restored (snapshot commit kept under refs/autosys/).")


def cmd_checkpoints(_yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    cps = _load_checkpoints(root)
    if not cps:
        info("No checkpoints yet — run `autosys checkpoint`.")
        return
    table = Table(title="Checkpoints", box=box.SIMPLE_HEAVY)
    table.add_column("#", justify="right")
    table.add_column("Label", style="bold")
    table.add_column("Created")
    table.add_column("Snapshot")
    for i, cp in enumerate(reversed(cps), 1):
        table.add_row(str(i), cp.get("label", "?"), cp.get("created", "?"), cp.get("sha", "?")[:10])
    console.print(table)


def cmd_restore(yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    cps = _load_checkpoints(root)
    if not cps:
        fail("No checkpoints to restore from — run `autosys checkpoint` first.")
    if working_changes(root) > 0 and not ask_confirm("Working tree has changes — discard them?", yes, default=False):
        warn("Aborted — stash or commit first.")
        return
    labels = [f"{cp.get('created', '?')} — {cp.get('label', '?')}" for cp in cps]
    choice = pick_from(labels, "Pick a checkpoint:")
    if choice is None:
        warn("Aborted.")
        return
    idx = labels.index(choice)
    cp = cps[idx]
    sha = cp.get("sha")
    if not sha:
        fail("Checkpoint has no snapshot SHA — re-create it.")
    ref = cp.get("ref") or f"refs/autosys/checkpoint-{int(time.time())}"
    if not yes:
        console.print(Panel(
            f"[yellow]Restoring to [bold]{cp.get('label', '?')}[/] will overwrite the working tree.[/]\n"
            f"Snapshot: [cyan]{sha[:10]}[/] ({cp.get('created', '?')})",
            border_style="yellow",
        ))
        if not ask_confirm("Proceed?", yes, default=False):
            warn("Aborted.")
            return
    orig = git(root, "rev-parse", "HEAD").stdout.strip()
    r = git(root, "reset", "--hard", sha)
    if r.returncode != 0:
        fail(f"Restore failed: {r.stderr.strip()}")
    if orig and orig != sha:
        git(root, "reset", "--soft", orig)
        info("Branch preserved — the reverted changes are staged; commit them when ready.")
    ok(f"Restored to [bold]{cp.get('label', '?')}[/] ({sha[:10]})")


# --------------------------------------------------------------------------
# Finish — release pipeline
# --------------------------------------------------------------------------

def cmd_finish(yes: bool = False) -> None:
    root = repo_root() or fail("Not inside a git repository — cd into a project first.")
    repo = remote_repo(root)
    has_remote = repo is not None
    console.print(Panel("[bold cyan]Release pipeline[/] — `autosys finish`", box=box.ROUNDED))

    TOTAL_STEPS = 6
    step_no = 0
    content = ""

    def step(name: str) -> None:
        nonlocal step_no
        step_no += 1
        console.print(f"\n[bold cyan]Step {step_no}/{TOTAL_STEPS}[/] — {name}")

    def step_ok(msg: str) -> None:
        console.print(f"  [green]OK[/] {msg}")

    def step_fail(step_name: str, p: subprocess.CompletedProcess, hint: str) -> None:
        err_console.print(f"[bold red]X Step {step_name} failed[/] (exit code {p.returncode})")
        tail = (p.stderr or p.stdout or "").strip()[-600:]
        if tail:
            err_console.print(f"  [red]{tail}[/]")
        err_console.print(f"[yellow]Fix: {hint}[/]")
        sys.exit(1)

    def local_tag_sha(tag: str) -> str | None:
        p = git(root, "rev-list", "-n", "1", tag)
        return p.stdout.strip() if p.returncode == 0 else None

    def remote_has_ref(ref: str) -> bool:
        if not has_remote:
            return False
        p = git(root, "ls-remote", "--exit-code", "origin", ref)
        return p.returncode == 0

    # -------- detect an in-flight (half-completed) release --------
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    head_msg = git(root, "log", "-1", "--pretty=%s").stdout.strip()
    pending_ver: str | None = None
    m = re.match(r"^chore\(release\):\s*v?(\d+\.\d+\.\d+)$", head_msg)
    if m:
        pending_ver = m.group(1)
    else:
        lt = latest_tag(root)
        if lt and local_tag_sha(lt) == head:
            pending_ver = lt[1:] if lt.startswith("v") else lt
    if not pending_ver:
        pv = primary_version(root)
        lt = latest_tag(root)
        if pv and lt:
            try:
                if parse_semver(pv) > parse_semver(lt):
                    pending_ver = pv
            except TypeError:
                pass
    recovering = pending_ver is not None
    tag_name = f"v{pending_ver}" if pending_ver else ""

    # ---- Step 1: preflight ----
    step("Preflight")
    if not has_remote:
        warn("No git remote configured - commit + tag will be local only (no push / no verification).")
    dirty = working_changes(root)
    if dirty:
        err_console.print(f"[bold red]X Step 1 failed:[/] working tree has {dirty} change(s):")
        for l in git(root, "status", "--porcelain").stdout.splitlines()[:10]:
            err_console.print(f"  [red]{l}[/]")
        err_console.print("[yellow]Fix: commit everything first (try `autosys commit`).[/]")
        sys.exit(1)
    uname = git(root, "config", "user.name").stdout.strip()
    uemail = git(root, "config", "user.email").stdout.strip()
    if not (uname and uemail):
        err_console.print("[bold red]X Step 1 failed:[/] git identity not set")
        err_console.print("[yellow]Fix: git config user.name 'Your Name' && git config user.email 'you@x.com'[/]")
        sys.exit(1)
    step_ok(f"clean tree | {uname} <{uemail}> | branch {current_branch(root)}"
            + (f" | remote {repo[0]}/{repo[1]}" if has_remote else ""))

    # ---- Step 2: tests ----
    step("Tests")
    test_cmd = None
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tox.ini").exists():
        test_cmd = [sys.executable, "-m", "pytest", "-q"]
    elif (root / "package.json").exists():
        try:
            scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts", {})
            if scripts.get("test"):
                test_cmd = ["npm", "test", "--silent"]
        except Exception:
            pass
    elif (root / "Makefile").exists():
        test_cmd = ["make", "test"]
    if recovering:
        step_ok(f"skipped - release v{pending_ver} already passed this step in a previous run (resume mode)")
    elif not test_cmd:
        warn("No test framework detected - skipping tests. Add pytest / a `test` script to be safe.")
    else:
        run_cmd = (["cmd", "/c"] if os.name == "nt" and test_cmd[0] in ("npm", "npx") else []) + test_cmd
        info(f"Running: {' '.join(run_cmd)}")
        try:
            p = subprocess.run(run_cmd, cwd=str(root), capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            fail("Tests timed out after 600s - run them manually to see where they hang.")
        except FileNotFoundError:
            fail(f"Test runner not found: {test_cmd[0]} - install it first.")
        if p.returncode != 0:
            err_console.print(f"[bold red]X Step 2 failed:[/] tests exited with code {p.returncode}")
            tail = (p.stdout or p.stderr or "").strip()[-400:]
            if tail:
                err_console.print(f"  [red]{tail}[/]")
            err_console.print("[yellow]Fix: run the failing tests, fix them, commit, and rerun `autosys finish`.[/]")
            sys.exit(1)
        step_ok("all tests passed")

    # ---- Step 3: version ----
    step("Version")
    vfiles = detect_version_files(root)
    if recovering:
        new_ver = pending_ver
        step_ok(f"resuming release at v{new_ver}")
        for f in vfiles:
            if f["version"] != new_ver:
                set_version(root, f, new_ver)
                ok(f"  healed {f['path']} -> {new_ver}")
    else:
        current = primary_version(root) or latest_tag(root) or "0.1.0"
        parsed = parse_semver(current) or (0, 1, 0)
        kinds = ["patch", "minor", "major"]
        if yes:
            bump = "patch"
        else:
            picked = pick_from(kinds, f"Bump kind (current {current}):")
            bump = picked or "patch"
        new_ver = bump_semver(parsed, bump)
        tag_name = f"v{new_ver}"
        if local_tag_sha(tag_name):
            err_console.print(f"[bold red]X Step 3 failed:[/] tag {tag_name} already exists locally "
                              f"(at {local_tag_sha(tag_name)[:8]})")
            err_console.print(f"[yellow]Fix: pick a higher bump, or delete the tag if it was a mistake: git tag -d {tag_name}[/]")
            sys.exit(1)
        if remote_has_ref(f"refs/tags/{tag_name}"):
            err_console.print(f"[bold red]X Step 3 failed:[/] tag {tag_name} already exists on origin - "
                              "a release for this version is already done")
            err_console.print("[yellow]Fix: use a higher version bump, or delete the remote tag first if it was never released.[/]")
            sys.exit(1)
        for f in vfiles:
            if f["version"] != new_ver:
                set_version(root, f, new_ver)
                ok(f"  {f['path']} -> {new_ver}")
    step_ok(f"version set to {new_ver}")

    # ---- Step 4: changelog ----
    step("Changelog")
    if recovering:
        content = f"Release v{new_ver} - see CHANGELOG.md for details."
        step_ok("already written in the previous run")
    else:
        since = latest_tag(root)
        content = build_changelog(root, since)
        if yes or confirm("Write CHANGELOG.md?", default=True):
            write_changelog(root, content)
            step_ok("CHANGELOG.md updated")
        else:
            step_ok("skipped (declined)")

    # ---- Step 5: commit + tag + push ----
    step("Commit + tag + push")
    if recovering:
        if not local_tag_sha(tag_name):
            p = git(root, "tag", tag_name)
            if p.returncode != 0:
                step_fail("5", p, "tag creation failed - inspect the error above")
            step_ok(f"tag {tag_name} re-created at HEAD")
        else:
            step_ok(f"tag {tag_name} already exists locally - reusing it")
    else:
        msg = f"chore(release): {new_ver}"
        git(root, "add", "-A")
        p = git(root, "commit", "-m", msg)
        if p.returncode != 0:
            step_fail("5", p, "release commit failed (often a pre-commit hook) - fix it and rerun `autosys finish`")
        step_ok(f"committed release {new_ver}")
        p = git(root, "tag", tag_name)
        if p.returncode != 0:
            if local_tag_sha(tag_name):
                warn(f"Tag {tag_name} already exists - reusing it.")
            else:
                step_fail("5", p, "tag creation failed - inspect the error above")
        else:
            step_ok(f"tagged {tag_name}")
    if has_remote:
        p = git(root, "push", "--follow-tags", "origin", current_branch(root))
        if p.returncode != 0:
            err_console.print(f"[bold red]X Step 5 failed:[/] push exited with code {p.returncode}")
            tail = (p.stderr or "").strip()[-600:]
            if tail:
                err_console.print(f"  [red]{tail}[/]")
            err_console.print(f"[yellow]Fix: the release commit + tag {tag_name} are safe locally. "
                              f"Rerun `autosys finish` to resume, or push manually: "
                              f"git push --follow-tags origin {current_branch(root)}[/]")
            sys.exit(1)
        step_ok("branch + tag pushed to origin")
    else:
        warn("No remote - skipped push (commit + tag are local).")

    # ---- Step 6: verification + GitHub release ----
    step("Verification + GitHub release")
    if not has_remote:
        step_ok(f"verified locally: commit {head[:8]} + tag {tag_name}")
        console.print(Panel(f"[green]Release complete (local only) - v{new_ver}[/]", box=box.ROUNDED))
        return

    branch = current_branch(root)
    rb = git(root, "ls-remote", "origin", f"refs/heads/{branch}").stdout.strip().split()
    if rb and rb[0] == head:
        step_ok(f"verified: origin/{branch} == {head[:8]}")
    else:
        err_console.print(f"[bold red]X Step 6 failed:[/] origin/{branch} is "
                          f"{rb[0][:8] if rb else 'missing'}, expected {head[:8]}")
        err_console.print(f"[yellow]Fix: git push origin {branch}[/]")
        sys.exit(1)

    lt_sha = local_tag_sha(tag_name) or ""
    rt = git(root, "ls-remote", "origin", f"refs/tags/{tag_name}").stdout.strip().split()
    if rt and rt[0] == lt_sha:
        step_ok(f"verified: origin tag {tag_name} == {lt_sha[:8]}")
    else:
        err_console.print(f"[bold red]X Step 6 failed:[/] tag {tag_name} not on origin "
                          f"(local {lt_sha[:8] or 'missing'})")
        err_console.print(f"[yellow]Fix: git push origin {tag_name}[/]")
        sys.exit(1)

    if repo and has_auth():
        api = GitHubAPI()
        full = f"{repo[0]}/{repo[1]}"
        existing = None
        try:
            existing = api.get(f"/repos/{full}/releases/tags/{tag_name}")
        except Exception:
            existing = None
        if existing and existing.get("id"):
            step_ok(f"GitHub release already exists: {existing.get('html_url', full)} - nothing to create")
        else:
            try:
                rel = api.create_release(full, tag_name, name=f"v{new_ver}",
                                         body=content[:4000], draft=True)
                step_ok(f"GitHub release created: {rel.get('html_url', '')} (draft)")
            except Exception as e:
                err_console.print(f"[bold red]X Step 6 failed:[/] GitHub release creation: {e}")
                err_console.print(f"[yellow]Fix: rerun `autosys finish` to resume, "
                                  f"or publish manually on {full}/releases[/]")
                sys.exit(1)
    elif repo:
        warn("Not logged in - GitHub release skipped. Run `autosys login` first.")

    console.print(Panel(f"[green]Release complete - pushed & verified: v{new_ver} "
                        f"on origin/{branch} + tag {tag_name}[/]", box=box.ROUNDED))


def cmd_repos(yes: bool = False) -> None:
    if not has_auth():
        fail("Not logged in — run `autosys login` first.")
    api = GitHubAPI()
    console.print("[cyan]Fetching your repos…[/]")
    repos = api.list_repos()
    if not repos:
        warn("No repos found.")
        return
    table = Table(title="Your repos", box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="bold")
    table.add_column("Private")
    table.add_column("Stars", justify="right")
    table.add_column("Language")
    table.add_column("Updated", style="dim")
    for r in repos:
        table.add_row(
            r["full_name"],
            "🔒" if r["private"] else "🌐",
            str(r.get("stargazers_count", 0)),
            r.get("language") or "—",
            (r.get("pushed_at") or "")[:10],
        )
    console.print(table)
    if repos:
        choice = pick_from([r["full_name"] for r in repos], "Clone one? (Enter skips)")
        if choice:
            p = git(None, "clone", f"https://github.com/{choice}.git")
            if p.returncode != 0:
                err_console.print(f"[bold red]Clone failed:[/] {p.stderr.strip()}")
            else:
                ok(f"Cloned [bold]{choice}[/]")


def cmd_repo_create(args: list[str], yes: bool = False) -> None:
    if not has_auth():
        fail("Not logged in — run `autosys login` first.")
    name = args[0] if args else ask("Repo name", default="my-project")
    private = yes or confirm("Private repo?", default=True)
    desc = ask("Description (optional)", default="") if not yes else ""
    api = GitHubAPI()
    try:
        repo = api.create_repo(name, private=private, description=desc, auto_init=True)
        ok(f"Created [bold]{repo['full_name']}[/] — {repo['html_url']}")
    except RuntimeError as e:
        fail(str(e))


def cmd_repo_release(args: list[str], yes: bool = False) -> None:
    if not has_auth():
        fail("Not logged in — run `autosys login` first.")
    repo = args[0] if args else None
    if not repo:
        root = repo_root()
        rr = remote_repo(root) if root else None
        repo = f"{rr[0]}/{rr[1]}" if rr else ask("Repo (owner/name)", default="")
    if "/" not in repo:
        fail("Expected repo in owner/name format.")
    tag = args[1] if len(args) > 1 else None
    if not tag:
        latest = latest_tag(root) if (root := repo_root()) else None
        tag = ask("Tag", default=latest or "v1.0.0")
    api = GitHubAPI()
    try:
        rel = api.create_release(repo, tag, name=tag, body="", draft=True)
        ok(f"Draft release created: {rel.get('html_url', '')}")
    except RuntimeError as e:
        fail(str(e))


# --------------------------------------------------------------------------
# Auth commands
# --------------------------------------------------------------------------

def cmd_login(args: list[str], no_browser: bool = False) -> None:
    cid = None
    for i, a in enumerate(args):
        if a == "--client-id" and i + 1 < len(args):
            cid = args[i + 1]
    client_id = get_client_id(cid)
    try:
        result = device_flow(client_id, GH_SCOPE, no_browser=no_browser)
    except RuntimeError as e:
        fail(str(e))
    auth = {"token": result["token"], "user": result["user"],
            "login_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    method = save_auth(auth)
    user = result["user"]
    ok(f"Logged in as [bold]{user.get('login')}[/] ({user.get('name') or 'no name'})")
    info(f"Token stored with {method} encryption in {AUTH_FILE}")
    if method == "file":
        warn("DPAPI unavailable on this system — token saved with file permissions only.")


def cmd_logout(_yes: bool = False) -> None:
    if not has_auth():
        info("Not logged in.")
        return
    save_auth({})
    ok("Logged out. Token removed.")


def cmd_whoami(_yes: bool = False) -> None:
    if not has_auth():
        fail("Not logged in — run `autosys login` first.", 1)
    auth = load_auth()
    user = auth.get("user", {})
    if isinstance(user, dict) and user.get("login"):
        console.print(f"[bold cyan]{user['login']}[/] {user.get('name') or ''} — logged in {auth.get('login_at', '?')}")
    else:
        info("Logged in (token present), user details unavailable.")


# --------------------------------------------------------------------------
# Interactive menu + dispatch
# --------------------------------------------------------------------------

MENU_ITEMS = [
    ("status", "Ship-readiness report (grade + verdict)"),
    ("commit", "Interactive commit + push + tag wizard"),
    ("secrets", "Scan for leaked secrets"),
    ("drift", "Detect version drift"),
    ("checkpoint", "Save a project state snapshot"),
    ("checkpoints", "List saved checkpoints"),
    ("restore", "Restore to a checkpoint"),
    ("explain", "Git history as a story"),
    ("doctor", "Full diagnosis with fixes"),
    ("finish", "Release pipeline (tests → bump → tag → release)"),
    ("repos", "Browse / clone your GitHub repos"),
    ("init", "Initialize project memory (.autosys)"),
    ("whoami", "Show GitHub login status"),
    ("logout", "Log out of GitHub"),
]


def interactive() -> None:
    print_banner()
    root = repo_root()
    mem = load_project_memory(root) if root else {}
    status = f"[bold]{root}[/]" if root else "[yellow]not a git repo[/]"
    logged = has_auth()
    console.print(f"Repo: {status}  |  GitHub: {'[green]logged in[/]' if logged else '[yellow]not logged in[/]'}")
    if root and not mem:
        console.print("[dim]Tip: run `autosys init` to save project preferences.[/]")
    while True:
        console.print("")
        labels = [f"[bold]{cmd}[/] — {desc}" for cmd, desc in MENU_ITEMS]
        choice = pick_from(labels, "What do you want to do? (q to quit)")
        if choice is None:
            warn("Bye!")
            return
        cmd = choice.split(" — ")[0].replace("[bold]", "").replace("[/]", "").strip()
        if cmd in ("commit", "checkpoint", "checkpoints", "restore"):
            if not root:
                fail("Not inside a git repository.")
        if cmd == "commit":
            cmd_commit()
        elif cmd == "status":
            run_check(root)
        elif cmd == "secrets":
            cmd_secrets()
        elif cmd == "drift":
            cmd_drift()
        elif cmd == "checkpoint":
            cmd_checkpoint()
        elif cmd == "checkpoints":
            cmd_checkpoints()
        elif cmd == "restore":
            cmd_restore()
        elif cmd == "explain":
            cmd_explain([])
        elif cmd == "doctor":
            cmd_doctor()
        elif cmd == "finish":
            cmd_finish()
        elif cmd == "repos":
            cmd_repos()
        elif cmd == "init":
            cmd_init()
        elif cmd == "whoami":
            cmd_whoami()
        elif cmd == "logout":
            cmd_logout()


def help_text() -> str:
    return f"""{APP_NAME} v{VERSION} — {TAGLINE}

Usage:
  autosys                    interactive menu
  autosys <command> [args]   direct command

Commands:
  login [--client-id <id>]   GitHub device-flow login (OAuth)
  logout / whoami            sign out / show login status
  init                       one-time project memory setup (.autosys/)
  status | check             ship-readiness report with A–F grade
  commit                     interactive commit + push + tag wizard
  drift [--fix]              detect & align version drift
  secrets                    scan repo for leaked secrets
  checkpoint                 save a project state snapshot
  checkpoints                list snapshots
  restore                    restore project to a checkpoint
  explain [file]             git history as a story
  doctor                     full diagnosis with suggested fixes
  finish                     release pipeline (tests → bump → changelog → tag → release)
  repos                      browse / clone your GitHub repos
  repo create <name>         create a new GitHub repo
  repo release <owner/name> [tag]   create a draft GitHub release
  version                    show version

Global flags:
  -y, --yes        accept defaults / skip prompts
  -V, --version    show version and exit
  -h, --help       show help
"""


def main(argv: list[str] | None = None) -> None:
    args = (argv if argv is not None else sys.argv)[1:]
    if not args:
        interactive()
        return

    yes = False
    no_browser = False
    cleaned: list[str] = []
    for a in args:
        if a in ("-y", "--yes"):
            yes = True
        elif a in ("-V", "--version"):
            print_banner()
            console.print(f"[bold cyan]{APP_NAME} {VERSION}[/] — {TAGLINE}")
            return
        elif a in ("-h", "--help", "help"):
            console.print(help_text())
            return
        elif a == "--no-browser":
            no_browser = True
        else:
            cleaned.append(a)
    args = cleaned
    cmd = args[0] if args else ""
    rest = args[1:]

    if cmd in ("status", "check"):
        cmd_status(yes)
    elif cmd == "commit":
        push = True if yes else None
        cmd_commit(yes, push=push)
    elif cmd == "secrets":
        cmd_secrets(yes)
    elif cmd == "drift":
        cmd_drift(yes or "--fix" in rest)
    elif cmd == "checkpoint":
        cmd_checkpoint(yes)
    elif cmd == "checkpoints":
        cmd_checkpoints(yes)
    elif cmd == "restore":
        cmd_restore(yes)
    elif cmd == "explain":
        cmd_explain(rest)
    elif cmd == "doctor":
        cmd_doctor(yes)
    elif cmd == "finish":
        cmd_finish(yes)
    elif cmd == "repos":
        cmd_repos(yes)
    elif cmd == "init":
        cmd_init(yes)
    elif cmd == "login":
        cmd_login(rest, no_browser=no_browser)
    elif cmd == "logout":
        cmd_logout(yes)
    elif cmd == "whoami":
        cmd_whoami(yes)
    elif cmd == "version":
        print_banner()
        console.print(f"[bold cyan]{APP_NAME} {VERSION}[/] — {TAGLINE}")
    elif cmd == "repo" and rest and rest[0] == "create":
        cmd_repo_create(rest[1:], yes)
    elif cmd == "repo" and rest and rest[0] == "release":
        cmd_repo_release(rest[1:], yes)
    else:
        err_console.print(f"[bold red]Unknown command: {cmd}[/]")
        console.print(help_text())
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
