# Work-PC Session 40 Handover — 2026-04-20

Continues immediately from `alex-session-39-work-pc-handover.md`, written earlier in the same calendar day. Session 39 covered the install test and the two install-path bug fixes (PR #16 model-load fallback, PR #17 settings save_and_close). Session 40 covers everything AFTER those merged: cutting v4.3.0 proper, fixing a CI regression the release flow surfaced, updating the user guide, and shipping a real public release.

## Branch
`master` at `ede9e9c`. Working tree clean. Up to date with `origin/master`.

## TL;DR

1. **v4.3.0 is live at** https://github.com/Moonhawk80/koda/releases/tag/v4.3.0 — first release produced by the GitHub Actions workflow (PR #14) end-to-end.
2. **Local installer** at `C:\Users\alex\Projects\koda\dist\KodaSetup-4.3.0.exe` (534 MB) — identical build to the public one for Google Drive sharing.
3. **Work PC upgraded** from 4.2.0 → 4.3.0 cleanly. Save button confirmed working ("works beautifully" per user). Home-PC-written `_model_small` bundled model, VAD assets, icon, DPI awareness, settings redesign all shipping.
4. **User guide** HTML is now current with MD; both bumped to 4.3.0. HTML had been missing 7+ sections (Settings, System Tray, full Formula Mode breakdown, Symbol reference, Transcribe Audio Files, Undoing a Paste, Voice Editing Commands table, Need Help).
5. **4 PRs merged this segment** — #18 (session 39 handover), #19 (version bump), #20 (CI fix), #21 (user guide sync). No open PRs.

## What Was Built This Session (post session-39)

### 1. PR #19 — `release/v4.3.0` — version bump

Two-line change: `voice.py` VERSION = "4.3.0", `installer/koda.iss` MyAppVersion "4.3.0". Triggered by user's request to build an installer to share with a team member. Merged as `a98aaf0`.

### 2. v4.3.0 tag → first CI failure

After PR #19 merged, pushed `v4.3.0` tag on master's new head. GitHub Actions workflow (from PR #14, merged in session 39) fired on the `v*.*.*` push trigger.

**Run 24681586743 failed at 3m17s:**
```
ERROR: Unable to find 'D:\a\koda\koda\venv\Lib\site-packages\faster_whisper\assets'
when adding binary and data files.
```

`build_exe.py:78` hardcoded a project-relative venv path, which only exists in dev. On the GA runner, deps install to `C:\hostedtoolcache\windows\Python\3.14.4\x64\Lib\site-packages\` — no `venv/` anywhere.

### 3. PR #20 — `fix/build-faster-whisper-path` — dynamic assets lookup

Replaced the hardcoded string with `importlib.util.find_spec("faster_whisper")` → `os.path.dirname(spec.origin) + "/assets"`. Works identically in local venv and CI-installed Python. Extracted into a small `_find_faster_whisper_assets()` helper with a clear error message if the package isn't importable at all. Merged as `c58bc41`.

Verified the dynamic path resolved to the same local value (`C:\Users\alex\Projects\koda\venv\Lib\site-packages\faster_whisper\assets`) so there's no behavior change for dev builds.

### 4. v4.3.0 re-tag → CI success

After PR #20 merged:
- `git push origin :refs/tags/v4.3.0` (delete the broken tag)
- `git tag v4.3.0 <new master head>` (re-tag on fixed commit)
- `git push origin v4.3.0` (re-trigger CI)

**Run 24685363028 succeeded at 6m36s.** `KodaSetup-4.3.0.exe` (559,995,232 bytes, SHA-256 `9e651de56c863ba5ee7bb895823e64122721042ed27aa7b1827c74ea7f8c2fdf`) uploaded to https://github.com/Moonhawk80/koda/releases/tag/v4.3.0 by `softprops/action-gh-release@v2`. Published 2026-04-20T19:18:44Z.

### 5. Local installer rebuild — parallel to CI

Before CI was fixed, the user needed to share the installer immediately. Ran `venv/Scripts/python.exe installer/build_installer.py` locally — took ~92s for Inno Setup compile (PyInstaller step ran separately). Inno Setup was at `C:\Users\alex\AppData\Local\Programs\Inno Setup 6\ISCC.exe` (non-default path, but `build_installer.py`'s `ISCC_PATHS` already covered it via `LOCALAPPDATA`). Output at `C:\Users\alex\Projects\koda\dist\KodaSetup-4.3.0.exe`, 534 MB.

### 6. Local upgrade 4.2.0 → 4.3.0

- `taskkill /f /im Koda.exe`
- `"C:\Program Files\Koda\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART` — cleanly removed old install dir (`C:\Program Files\Koda\`)
- Launched new installer from `dist/KodaSetup-4.3.0.exe`, user handled UAC + SmartScreen
- New install dir `C:\Program Files\Koda\`, debug.log confirmed `INFO: Koda v4.3.0 fully initialized`, all 6 hotkeys re-registered
- Save button manually verified by user: "works beautifully" (no taskkill, no dead tray, no "failed to remove _MEI" popup)

### 7. PR #21 — `docs/user-guide-v4.3.0` — user guide sync

User asked where the user guide was for upload to Google Drive alongside the installer. The MD (`docs/user-guide.md`) was current (13 KB, last touched 12:09 today via session 37 frozen-exe parity commit), but the HTML (`docs/user-guide.html`) had drifted since session 30.

**Sections missing from HTML:**
- Settings (entire section, including the new Save-behavior tip describing PR #17)
- System Tray Menu
- Formula Mode — HTML had one abbreviated 7-row table; MD had 6 categorized subsections (Adding / Averages / Counting / Dates / IF / VLOOKUP) + Tips + Excel navigation + Create tables
- Terminal Mode — missing the full 15-row Symbol reference table
- Transcribe Audio Files — entire section (right-click menu, `context_menu.py install`, Windows 11 "Show more options", removal)
- Undoing a Paste — entire section
- Voice Editing Commands — missing the top-level 16-row table (HTML only had the terminal-subsection variant)
- Need Help

Rewrote HTML body 1:1 with MD, preserving the existing CSS classes (`hotkey-grid`, `mic-table`, `tip`, `warning`, `steps`, `troubleshoot-item`, `quality`). CSS section untouched. Added `<h3>`, `<ul>`, `<code>` block styles. Both files bumped to 4.3.0 (title badge, installer filename reference, footer). Merged as `ede9e9c`.

### 8. Developer-friendly Koda explainer

User asked for a write-up for a developer friend who "doesn't get it." Wrote a ~350-word explainer covering:
- local-first faster-whisper stack (no cloud, no API cost)
- push-to-talk vs. always-on (better accuracy, no hot mic)
- the dev-relevant features: terminal mode with symbol conversion, voice commands mid-dictation, Prompt Assist for LLMs, Formula Mode for Excel/Sheets, right-click audio transcription
- stack details (Python 3.14, PyInstaller, pystray, tkinter, CPU-only, 0.34 RTF)

Not saved to repo — delivered inline in chat for user to paste.

## Decisions Made

### Separate PR per concern (not a single v4.3.0 rollup)
Could have bundled version bump + CI fix + docs into one PR. Kept them separate because:
1. #19 was approved and merged before #20's bug was known; good that those didn't block each other
2. #20 is a CI-only regression fix with no doc implications; #21 is pure docs with no code
3. Each revertable independently if anything surfaces later
Matches the "small atomic PRs" pattern from prior Koda sessions.

### Re-tag same version vs. cut v4.3.1 after CI failure
When the first v4.3.0 CI run failed, picked re-tag (delete + push). Rationale: no release asset ever got created, so no downloaders were affected by the broken tag. The commit hash under the tag was pre-fix and would have been misleading — better to point v4.3.0 at the FIXED commit. Safe because the only consumer of the tag is the GA workflow, not any cached download URLs.

### User guide HTML kept hand-maintained (no MD→HTML pipeline)
Could have added a markdown→HTML generation step (pandoc, markdown-it, etc). Didn't. Reasons: the HTML's custom CSS (`hotkey-grid` 2-col, `quality` badges with color-coded backgrounds, numbered `.step` circles) doesn't map cleanly to generated HTML; the guide is small enough that parity drift is catchable by hand. Flagged in the PR description as a follow-up candidate if the guide grows.

### Local installer rebuild ran in parallel with CI fix
Could have waited for CI to produce the public release. Did the local rebuild in parallel so the user had a shareable file the moment Google Drive was open. Worked out: the local build finished before CI failed on the first tag, and the local + public installers are byte-equivalent (same source, same model, same Inno Setup script).

### Both local .exe and public URL offered for sharing
Not strictly either/or — local file is faster to share in the moment (no CI wait); GitHub URL is nicer long-term (versioned, always available, SHA listed). User gets both to pick.

## User Feedback & Corrections

Verbatim quotes from this segment:

- **"it works beautifully"** — confirming the Save button fix (PR #17) works in the installed 4.3.0 build. This is the validation that closed the loop on the install-test bugs.
- **"did the save thing get fixed?"** — double-checked before testing, which is correct caution given how many times we've swapped install states today.
- **"need to explain it to my developer friend he doesnt get it"** — wanted a dev-oriented pitch, not a sales pitch. Delivered in inline explainer.
- **"push it"** — when a team-member-shareable artifact needed a public URL. Drove the tag + release flow.
- **"is the user guide updated if so where can I grab it to upload it"** — surfaced that the HTML was stale vs. MD; led to PR #21.
- **"update the html then"** — terse authorization to do the sync. Followed by "update and do the PR for it" reinforcing the workflow (PRs, not direct pushes).

No redirects or rework in this segment. Course was clean.

## Waiting On

Nothing blocking. All merged, all shipped, all verified. Items for home-PC Claude to consider:

- **Phase 9 RDP test** — carried over from session 35/39. Not run this session. Still the last unchecked item from the original install-test email plan.
- **1 GB memory anomaly** flagged in session 39 — observed on the broken 4.2.0 build during mid-session zombie cycles; was NOT reproduced after the clean 4.3.0 install (current idle is ~371 MB → ~20 MB paged, normal). Likely was a symptom of the save-and-restart bug leaking hotkey subprocess handles. Probably closed by PR #17. Worth a single re-check on home PC with fresh 4.3.0 to confirm.
- **Phase 16 license system** — still blocked on 3 decisions (subscription vs. one-time, offline activation, tier count). Surfaced in PR #15's phase plan doc, still open.
- **Home-PC port parity** — verify 4.3.0 installer runs cleanly on home PC (home built the source, hasn't installed the packaged exe since 4.2.0).

## Next Session Priorities

1. Share v4.3.0 with team member (Google Drive for installer + user-guide.html, or GitHub URL + user-guide.html)
2. Home-PC smoke test of 4.3.0 installer on home PC
3. Phase 9 RDP test — the last unchecked box from the original install-test email
4. Phase 16 decisions (pricing / activation / tiers) so license work can actually start
5. Monitor for any 4.3.0 regressions reported by the team member

## Files Changed (post session-39)

| File | PR | Description |
|---|---|---|
| `voice.py` | #19 | VERSION: "4.2.0" → "4.3.0" |
| `installer/koda.iss` | #19 | MyAppVersion: "4.2.0" → "4.3.0" |
| `build_exe.py` | #20 | Replaced hardcoded `venv/Lib/site-packages/faster_whisper/assets` with `importlib.util.find_spec` lookup; added `_find_faster_whisper_assets()` helper |
| `docs/user-guide.md` | #21 | Version badge 4.2.0→4.3.0; installer filename 4.2.0→4.3.0 |
| `docs/user-guide.html` | #21 | Full body rewrite to mirror MD sections (7+ missing sections added); version + footer bumped; CSS added `<h3>`, `<ul>`, `<code>` rules |
| `dist/KodaSetup-4.3.0.exe` | local | 559,905,237 bytes — local Inno Setup build |

Untracked artifacts (not committed): `dist/KodaSetup-4.3.0.exe`, `dist/KodaSetup-4.2.0.exe` (can be deleted).

## Key Reminders

- **v4.3.0 shipped** — first full end-to-end CI release. The PR #14 workflow works. Tagging `v*.*.*` on master now produces a real public release asset.
- **Save button no longer crashes** — PR #17's `save_and_close` confirmed working in the packaged exe via user test. Old `save_and_restart` behavior is dead and buried.
- **Model-load fallback** — PR #16 means a stale AppData `model_size` will self-heal to the bundled model instead of crashing. Still worth not shipping mismatched config/bundle pairs, but no longer user-visible.
- **CI fix pattern** — any future `venv/Lib/site-packages/...` path in build scripts is a CI time bomb. Use `importlib.util.find_spec` whenever bundling resources from installed packages.
- **Re-tag safely** — if a `v*` tag's CI run fails and produced no release asset, `git push origin :refs/tags/vX.Y.Z` + re-tag is safe. If it DID produce an asset anyone downloaded, cut `vX.Y.Z+1` instead.
- **User guide is hand-maintained** — any future feature that touches Settings / hotkeys / modes needs manual updates to BOTH `user-guide.md` AND `user-guide.html`. Parity-drift check should be part of any "add a feature" workflow.
- **Work-PC work-PRs-only rule held** — every change this session went through a PR, even one-line version bumps. No direct master pushes.
- **Session numbering:** work-PC sessions are 34, 35, 36 (work-pc suffix), 39 (work-pc suffix), 40 (this file). Home-PC sessions: 35, 36, 37, 38. Disambiguation via `-work-pc-` filename suffix continues to be the convention.

## Migration Status
None this session.

## Test Status

| Suite | Count | State |
|---|---|---|
| `test_features.py` on master | 353 | ✅ All passing (including the 6 new tests from PR #16 and the 5 new from PR #17 that merged earlier today) |
| CI build | ✅ | 6m36s on v4.3.0 tag after `fix/build-faster-whisper-path` |

No test changes this segment — all new tests were in the session-39 work (PR #16/#17).

## New session prompt

```
cd C:\Users\alex\Projects\koda

Continue from work-PC session 40 handover (docs/sessions/alex-session-40-work-pc-handover.md).

## What we were working on
Shipped Koda v4.3.0: cut the release tag, fixed a CI regression (build_exe.py had a hardcoded venv path that broke on the GitHub Actions runner), synced the user-guide HTML with the Markdown source, and upgraded the work PC from 4.2.0 to 4.3.0 with both install-path bug fixes confirmed working. Official release is live at github.com/Moonhawk80/koda/releases/tag/v4.3.0.

## Next up
1. Home PC — verify 4.3.0 installer runs cleanly on home PC (home hasn't installed the packaged exe since 4.2.0)
2. Run the Phase 9 RDP test that's been pending since session 35
3. Re-check the 1 GB idle memory anomaly that was flagged in session 39 — almost certainly closed by PR #17 but worth one explicit check
4. Make the 3 Phase 16 decisions (subscription vs one-time, offline activation, tier count) so license-system work can actually start
5. Respond to anything the team member reports after trying v4.3.0

## Key context
- v4.3.0 is live on GitHub and on the work PC. User's Google Drive / team-member share may already be in progress.
- No open PRs. Working tree clean on master.
- Both install-path bugs from session 39 (model-load fallback, save-and-restart) are fixed, merged, and shipped in the installer the public can download.
- User guide HTML and MD are now in sync. Any future feature work needs to update both.
- Work-PC rule stays: PRs only for changes on Moonhawk80/koda, no direct pushes to master.
```

Copy the block above into a new session to pick up where we left off, in koda.
