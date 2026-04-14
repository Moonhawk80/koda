# Alex Session 22 Handover — 2026-04-13

## Branch
`master` — fully pushed to origin. Latest commit: `5c7046f`

---

## What Was Built This Session

### 1. KodaSetup-4.2.0.exe — Built Successfully
Installed Inno Setup 6 (user installed manually), then ran `python installer/build_installer.py`.
Output: `dist/KodaSetup-4.2.0.exe` (529MB). Compiled clean with one warning (fixed).

**File:** `dist/KodaSetup-4.2.0.exe` — not in git (dist/ is gitignored). Distribute as GitHub Release asset.

### 2. Installer Warning Fix — `installer/koda.iss`
Added `RunOnceId: "KillKoda"` to the `[UninstallRun]` entry. Removes Inno Setup warning:
> "There are [UninstallRun] section entries without a RunOnceId parameter"

### 3. Critical Transcription Fix — `voice.py`
**Problem:** Every single Ctrl+Space press was failing silently. Transcription pipeline errored on every attempt since the hallucination fix was committed in session 19.

**Root cause:** Typo in the hallucination fix — `logprob_threshold` should be `log_prob_threshold`. faster-whisper's parameter name uses underscores differently. The error was logged (`[ERROR] Transcription pipeline error: WhisperModel.transcribe() got an unexpected keyword argument 'logprob_threshold'`) but not visible to user since they hadn't tried transcribing before this session.

**Fix:** `voice.py` line 620: `logprob_threshold` → `log_prob_threshold`

This means the hallucination protection (confidence threshold at -0.8) was never active until this fix. It is now working.

### 4. Select-All Fuzzy Aliases — `voice_commands.py`
**Problem:** Whisper small model transcribes "select all" as "select alt" — the command pattern didn't match, so it pasted the literal text instead of firing Ctrl+A.

**Fix:** Expanded the select-all regex from `r"select all"` to `r"select (?:all|alt|ole|hall|everything)"` to catch common small-model mishears.

**Reasoning:** Not adding fuzzy matching for everything — just the most common mishear for a high-value command. Pro tier users get larger models with better accuracy.

### 5. Startup Shortcut Fixed
**Problem:** Startup shortcut (`Koda.lnk` in Windows Startup folder) pointed to `start.bat`. Task Manager Startup tab showed a plain CMD icon with no description because Task Manager reads the icon from the target executable, not the shortcut's IconLocation property.

**Fix:** Changed shortcut target to `dist/Koda.exe` (has Koda icon embedded by PyInstaller). Now shows teal Koda icon + "Koda — Push-to-talk voice transcription" in Task Manager.

**Note:** Dev work still uses `start.bat` manually. Startup on boot uses `dist/Koda.exe`. Cold boot K1 test not yet run — user was about to reboot at end of session.

### 6. StartMenu crash (unrelated to Koda)
`StartMenuExperienceHost.exe` crashed when user enabled Koda in Task Manager Startup tab. Coincidence — this is a known Windows 11 issue where the Start menu process locks up randomly. Fixed with `taskkill //f //im StartMenuExperienceHost.exe` — Windows auto-restarts it.

---

## Decisions Made

### Pricing Revision
Discussed current pricing ($49 Personal, $89 Pro) being too low. Agreed on new pricing:
- **Personal: $79 one-time** — offline premium justifies over $15/mo cloud tools, still 68% under Superwhisper
- **Pro: $149 one-time** — legal/medical/RSI users compare to Dragon at $699; $149 is a steal
- **Updates: $29/yr** — deliberate commitment, not an afterthought
- **Free tier: unchanged** — top-of-funnel hook

**Why:** Dragon abandoned sub-$300 market in 2023. Superwhisper is $249 Mac-only. There is no direct Windows competitor at any price point.

### Tier Feature Split (Defined This Session)
| Tier | Key Features |
|------|-------------|
| Free | Hold-to-talk, small model, English only, smart punctuation, auto-capitalize, **30 transcriptions/day limit** |
| Personal ($79) | Unlimited, filler removal, snippets, number/date/email formatting, voice commands, stats, auto-updater |
| Pro ($149) | Medium/large model, custom vocabulary, per-app profiles, all 99 languages, prompt assist, case formatting, plugins |
| Updates ($29/yr) | All new versions for Personal and Pro |

**Reasoning:** 30/day free limit creates natural upgrade pressure without being hostile. Pro features map exactly to legal/medical/dev/RSI high-WTP segments.

### Phase 13 Scope Clarified
Phase 13 is NOT just building the installer — it's the full storefront + monetization phase:
1. Feature gates in code (free/Personal/Pro checks)
2. Offline HMAC license key system (no server)
3. LemonSqueezy store setup
4. Landing page at kodaspeak.com
5. Rebuild installer with trial mode baked in

The installer built this session is the delivery vehicle — currently ships everything ungated.

### Fuzzy Aliases: Case by Case
Decision: don't add fuzzy aliases for all commands — only for the most common, high-value mishears. Whack-a-mole approach is acceptable since Pro tier fixes accuracy via larger models anyway.

### Costs
User asked about ongoing costs — confirmed essentially zero:
- LemonSqueezy: 5% per transaction
- Domain: ~$12/yr
- No servers, no API bills, no hosting
- Whisper runs on user's machine

---

## User Feedback & Corrections

- **"I feel they are low as fuck"** — User's gut on original $49/$89 pricing was right. New pricing confirmed at $79/$149.
- **"we need to discuss and market research and deep analyze"** — User wanted a real analysis, not a rubber stamp. Competitor table + segment analysis provided before committing to new prices.
- **"but now inno is connected to my app?"** — User was concerned Inno Setup has runtime dependency on Koda. Clarified: it's a build tool only, not connected to the app at runtime.
- **"it is not transcribing at all on this pc"** — Led to discovery of the logprob_threshold typo that had been silently breaking all transcription since session 19. Critical find.
- **"start still shows plain and no info and it is disabled I wont enable it until you fix it"** — User won't enable startup until it looks professional. Fixed by pointing shortcut to Koda.exe.

---

## Waiting On

- **K1 — Cold boot test** — User was about to reboot at end of session. Test: press Ctrl+Space immediately after boot before doing anything else. Verify: keyboard doesn't freeze, transcription works.
- **KodaSetup-4.2.0.exe test on work PC** — Install on work PC, verify wizard shows logo + "by Alex Concepcion", hotkeys work post-install.
- **RDP test** — Connect to home PC via Chrome Remote Desktop (or Windows RDP) from work PC, press Ctrl+Space, verify it fires.
- **Settings UI visual polish** — User not happy with fonts/colors but said "can do for now" — deferred to later phase.
- **Phase 13 full build** — Feature gates, license keys, LemonSqueezy, landing page. Not started.

---

## Next Session Priorities

1. **K1 result** — User reboots, reports back. If keyboard freezes, that's P0. If it works, mark Phase 9 Test 1 done.
2. **Install KodaSetup-4.2.0.exe on work PC** — verify installer wizard branding + post-install Koda works
3. **RDP test** — from work PC, remote into home PC, verify Ctrl+Space fires
4. **Phase 13 kickoff** — start feature gate system design (free/Personal/Pro checks in code)

---

## Files Changed This Session

| File | Change |
|------|--------|
| `voice.py` | Fixed `logprob_threshold` → `log_prob_threshold` (critical — was breaking all transcription) |
| `voice_commands.py` | Added fuzzy aliases for select-all: alt, ole, hall, everything |
| `installer/koda.iss` | Added `RunOnceId: "KillKoda"` to UninstallRun entry |
| `dist/KodaSetup-4.2.0.exe` | Built this session — 529MB, not in git |

**Uncommitted (intentional — local only):**
- `CLAUDE.md` — session notes
- `config.json` — dev snippets + Zira TTS voice

---

## Key Reminders

- **Startup shortcut now points to `dist/Koda.exe`** — not start.bat. Dev work still uses start.bat manually. Do NOT change this back.
- **logprob_threshold was broken for 3 sessions** (sessions 19–22) — hallucination protection was never active until this session's fix. The H1/H3/H5 tests passing this session are the first real validation.
- **KodaSetup-4.2.0.exe is NOT uploaded to GitHub Release yet** — pending work PC install test before publishing
- **Phase 13 = storefront, not just installer** — easy to confuse. The exe is the delivery vehicle. The actual work is feature gates + license keys + LemonSqueezy + landing page.
- **New pricing: $79 Personal / $149 Pro / $29/yr updates** — not yet reflected anywhere in code or marketing
- **30/day free tier limit** — agreed in session but NOT yet implemented in code
- **Kill ALL python before restart:** `taskkill //f //im pythonw.exe` AND `taskkill //f //im python.exe`
- **Full test suite:** `venv/Scripts/python -m pytest test_features.py test_e2e.py -q` (208 tests)
- **StartMenu fix if it breaks again:** `taskkill //f //im StartMenuExperienceHost.exe`
- **No CUDA** — Intel UHD 770 only
- **settings_gui runs as pythonw** — save_and_restart kills parent by os.getppid() only

---

## Migration Status

None. No database changes this session.

---

## Test Status

| Suite | Count | Status |
|-------|-------|--------|
| `test_features.py` | 187 | ✅ All passing |
| `test_e2e.py` | 21 | ✅ All passing |
| `test_stress.py` | 17/17 | ✅ Standalone only |
| **Total** | **208** | **✅** |

### Manual Tests Run This Session
| Test | Result |
|------|--------|
| H1 — silence 3 sec | ✅ Nothing pasted |
| H3 — 30 sec speech | ✅ No hallucination, accurate |
| H5 — instant tap | ✅ Nothing pasted |
| T6 — "new line" command | ✅ Inserts newline |
| T7 — "select all" command | ✅ Fixed (was pasting text) |
| A1 — Settings tabs | ✅ All 5 tabs load |
| K1 — cold boot | ⏳ Pending reboot |
