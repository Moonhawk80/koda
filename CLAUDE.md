# Koda — Project Context

@../_shared/owner-profile.md
@../_shared/build-standards.md

## What Koda Is
Push-to-talk voice-to-text Windows system tray app. Personal productivity tool for Alexi — captures speech and pastes transcribed text into any active window (Claude, ChatGPT, Slack, email, etc.).

## Repo & Working Directory
- **Repo:** github.com/Moonhawk80/koda
- **Local path:** `C:\Users\alexi\Projects\koda`
- **Run from source:** `cmd //c "C:\Users\alexi\Projects\koda\start.bat"` — do NOT build/install exe during dev
- **Tests:** `venv/Scripts/python -m pytest test_features.py` (96 tests passing)

## Tech Stack
- Python 3.14, venv at `C:\Users\alexi\Projects\koda\venv`
- Hardware varies per dev machine — run `venv/Scripts/python system_check.py` (or `Koda.exe --detect-hardware --json`) for the authoritative classification. Home PC: i7-13650HX / 20 cores / 15.7GB / RTX 4060 Laptop + CUDA usable / **POWER tier**.
- test_stress.py runs standalone only (not via pytest normally)

## Known Issues / Environment Quirks
- `configure.py` fails with UnicodeEncodeError in bash (cp1252 console) — cosmetic only, config.json already present
- GPU Power Mode is testable on any POWER-tier machine. Trust `system_check.classify()` over any hardcoded assumption in this file.

## Current Status
See memory file for session-by-session state: `C:\Users\alexi\.claude\projects\C--Users-alexi\memory\project_koda.md`

## Pre-push quality gate (required for code changes)

Before opening a pull request or pushing any code change to GitHub:

1. Verify Skill Forge is current: `bash ~/Cortex/Projects/skillforge/scripts/check-updates.sh`. Exit 0 = proceed. Non-zero = resolve before continuing (install it, pull, or clean your local tree — the script tells you which). If the script is missing, Skill Forge isn't installed — see `~/Cortex/Projects/skillforge/README.md`.
2. Run `/forge-deslop` on the diff. Approve the hygiene fixes it proposes.
3. Run `/forge-review` on the diff. Resolve any BLOCKING or NEEDS-FIX findings.
4. Only then push.

**Scope:** applies to pushes that touch code (source files, migrations, config, package manifests). Docs-only, README-only, brand-file-only, or `.claude/next.md`-only pushes are exempt.

**Order matters:** check first (stale skill = false green), deslop second (may modify code), review third (validates the cleaned result). Reversing the order invalidates the review.
