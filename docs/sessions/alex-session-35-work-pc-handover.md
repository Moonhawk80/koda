# Alex Session 35 Handover — 2026-04-16

## Branch
`feat/github-actions-release-build` — 1 commit ahead of master. PR #14 OPEN at Moonhawk80/koda#14.

---

## What Was Built This Session

### 1. GitHub Actions Release Build Workflow (PR #14)

**File:** `.github/workflows/build-release.yml` (new)

Full CI/CD pipeline that triggers on version tag push (`v*.*.*`) and automatically builds + uploads the installer to GitHub Release. Steps:

1. Windows runner, Python 3.14
2. Installs deps from `requirements.txt` + PyInstaller
3. Caches Whisper small model (462 MB) in `~/.cache/huggingface` — key: `whisper-small-v1`
4. Downloads model on cache miss
5. Patches version in `koda.iss` from the tag (so `KodaSetup-4.3.0.exe` matches `v4.3.0`)
6. Runs `build_exe.py` (~10 min PyInstaller)
7. Installs Inno Setup via Chocolatey
8. Runs `installer/build_installer.py`
9. Uploads `KodaSetup-{version}.exe` to GitHub Release via `softprops/action-gh-release@v2`

**To use when ready:** `git tag v4.3.0 && git push origin v4.3.0`

### 2. build_exe.py — Dynamic Model Path Fix

**File:** `build_exe.py` (modified)

Replaced hardcoded Whisper snapshot hash:
```python
# OLD — breaks on CI and when Hugging Face updates the model
MODEL_DIR = os.path.expanduser("~/.cache/.../snapshots/536b0662742c02347bc0e980a01041f333bce120")

# NEW — finds whatever snapshot is present
def _find_whisper_model(model_name="small"):
    base = os.path.expanduser(
        f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{model_name}/snapshots"
    )
    if not os.path.isdir(base): return None
    snapshots = sorted(os.listdir(base))
    return os.path.join(base, snapshots[-1]) if snapshots else None
```

Also added `if MODEL_DIR and` guard on the `os.path.exists(MODEL_DIR)` check (was crashing when `MODEL_DIR` was `None`).

---

## Decisions Made

### Make repo private (discussed, not done yet)
**Why:** User intends to sell Koda commercially. Source being public = anyone can copy it. No license in the repo = all rights reserved by default, but making it private is cleaner protection.
**Action needed:** User does this in GitHub UI: github.com/Moonhawk80/koda → Settings → Danger Zone → Change visibility → Private.
**Impact on distribution:** Private repo = GitHub Release downloads require auth. Fix: use a separate public `koda-releases` repo or share installer via Google Drive/OneDrive for now.

### Current installer distribution after going private
**Decision:** For the immediate term (still stress testing), share `KodaSetup-4.2.0.exe` via Google Drive/OneDrive link with testers instead of the GitHub Release URL.
**Long term:** Two-repo setup (`koda` private for source, `koda-releases` public for releases) or proper distribution via Gumroad when ready to sell.

### GitHub Release bandwidth limits — not a concern
Clarified that GitHub Release download limits (what Alex was worried about) apply to GitHub Pages, not Releases. Release assets are CDN-served with no enforced limit for public repos.

### Future monetization stack noted (not built)
When ready to sell: Gumroad or Lemon Squeezy for payment/license delivery, a simple landing page (GitHub Pages or Carrd), and a license key/activation system to be built into the app. **None of this exists yet — Koda has no activation system.**

### PR #14 does not need live testing
The workflow only runs on tag push. Merge when ready; first real test is when cutting the next release tag.

---

## User Feedback & Corrections

- **Cost question:** User asked how much it costs to run Koda when people use prompt assist / translation. Answer: $0 — everything runs locally (faster-whisper, Ollama, pyttsx3, SileroVAD, OpenWakeWord). No external API calls anywhere.
- **"Yes" to testing on work PC:** User confirmed they want to do Block 4/5 live testing here on the work PC. Testing was set up (Koda started from source) but not yet executed — session ended before tests ran.
- **Repo privacy question:** User asked "should I make it private?" → answered with trade-offs → user asked about selling risk → outcome: make it private, but haven't done it yet.

---

## Waiting On

- **Repo made private** — user needs to do this in GitHub UI. After doing it, the v4.2.0 release URL will stop working for unauthenticated users. Need to re-host installer somewhere (Google Drive/OneDrive or set up koda-releases repo).
- **PR #14 merge** — Moonhawk80/koda#14 (GitHub Actions workflow). No live testing needed, can merge anytime.
- **Block 4 live testing** — NOT done this session. Koda was started from source but tests were not run:
  - Test 15: Correction mode (Ctrl+Alt+C) — paste something, press Ctrl+Alt+C, verify clear + re-record + paste replacement. Check debug.log for `Correction mode triggered`.
  - Test 16: Correction in terminal — same but in PowerShell, verify Escape clears line.
  - Test 17: Readback (Ctrl+Alt+R) — verify TTS reads back last dictation.
  - Test 18: Readback selected (F5) — select text, F5, verify TTS reads only selected.
- **Block 5 edge cases** — silent dictation, long dictation, background noise, "we should undo the changes" false positive.
- **Excel actions live test** — Ctrl+F9 in Excel: navigation, table creation, formula mode.
- **Phase planning** — user explicitly requested planning for next Koda phases. Not started.
- **Coworker follow-up** — share installer link (will need new URL after repo goes private).
- **Installer wizard test** — fresh install on a clean machine.

---

## Next Session Priorities

1. **Make repo private** — GitHub UI, 1 click. Then decide: Google Drive link for testers, or set up koda-releases repo.
2. **Merge PR #14** — GitHub Actions workflow. No testing needed.
3. **Block 4 live test** — run Tests 15–18 (correction mode + readback). Koda should be running from source already; if not, kill pythonw.exe and run start.bat.
4. **Block 5 live test** — edge cases.
5. **Excel actions** — Ctrl+F9 in Excel.
6. **Phase planning** — map out what comes after stress testing is done.

---

## Files Changed This Session

| File | Status | Description |
|---|---|---|
| `.github/workflows/build-release.yml` | Created | GitHub Actions CI/CD: builds installer on tag push |
| `build_exe.py` | Modified | Dynamic Whisper model path instead of hardcoded snapshot hash |
| `docs/sessions/alex-session-35-handover.md` | Created | This document |

---

## Key Reminders

- **Repo still public** — user intends to make it private but hasn't done it yet.
- **PR #14 is open** — `feat/github-actions-release-build`. Safe to merge anytime, no live testing needed.
- **Correction mode still unconfirmed** — VAD fix + logging were applied in PR #13 (last session) but live test was cut short. This is the highest-priority live test.
- **Work PC hotkeys:** Ctrl+Space (dictation), F8 (command), Ctrl+F9 (prompt), Ctrl+Alt+C (correction), Ctrl+Alt+R (readback), F5 (readback selected).
- **Kill before starting:** `taskkill //f //im Koda.exe && taskkill //f //im pythonw.exe`
- **Start from source:** `cmd //c "C:\Users\alex\Projects\koda\start.bat"`
- **339 tests passing** — no new tests this session.
- **No activation system** — Koda has no license key / DRM. Must be built before selling.
- **GitHub Actions cache key** — `whisper-small-v1`. Bump to `whisper-small-v2` if the model is upgraded.
- **PRs only for Moonhawk80** — no direct pushes to master.

---

## Migration Status

None this session.

---

## Test Status

| Suite | Count | Status |
|---|---|---|
| `test_features.py` | 339 | ✅ All passing |
| **Total** | **339** | **✅** |

No test changes this session.
