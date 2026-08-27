# Security Policy

AutoSys stores authentication tokens and analyzes source code, so security
matters here. Thanks for taking the time to report responsibly.

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.0.x   | ✅ Current release |
| < 2.0   | ❌ Pre-release builds (fixes were internal) |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.** Please report
privately:

- **GitHub:** use the *Report a vulnerability* tab on this repository
  (Security → Report a vulnerability) — it reaches the maintainers privately.
- **Email fallback:** if the repo's private reporting is unavailable, email the
  maintainer (address in the repository description/profile) with subject
  `[autosys-security]`.

Please include:

1. The affected version (`autosys version`).
2. OS + Python version.
3. A description of the vulnerability and its impact (confidentiality /
   integrity / availability).
4. Reproduction steps or a minimal PoC.
5. Any suggested fix (optional).

You should receive an acknowledgement **within 72 hours**, and a status update
within 7 days. We coordinate public disclosure after a fix ships — no
embargoed exploits published before that.

## Security Model (what we protect)

- **Token at rest** — GitHub OAuth tokens are encrypted with Windows DPAPI
  (`DPAPI1` blob); no plaintext token is ever written to disk. Non-Windows
  builds fall back to permission-protected files with a visible warning.
- **Token in transit** — device-flow OAuth over HTTPS to GitHub's official
  endpoints only.
- **Secret scanner** — flags leaked credentials before you push; bounded scans
  to avoid pathological repositories.
- **No telemetry** — AutoSys makes no network calls except the GitHub API
  features you explicitly invoke.

## Known considerations (not vulnerabilities)

- The default OAuth client ID is GitHub CLI's public ID so the device flow
  works out of the box. Production distributions **must** set
  `AUTOSYS_CLIENT_ID` to their own OAuth app ID (see MANUAL.md §13) — the
  public default may be subject to rate limits.
- `restore` semantics: restoring a checkpoint overwrites newer worktree
  changes to the same files (recoverable via git reflog). Confirm prompts
  carefully; see MANUAL.md §9.
