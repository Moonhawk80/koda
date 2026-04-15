# Koda User Guide
**Version 4.2.0**

---

## What is Koda?

Koda is a push-to-talk voice transcription tool for Windows. Press a hotkey, speak, and your words are instantly typed into whatever you're working in — emails, Slack, Word, Excel, ChatGPT, anything.

No clicking a mic button. No switching apps. Just talk.

---

## Installation

1. Double-click **KodaSetup-4.2.0.exe**
2. If Windows shows a "protected your PC" warning, click **More info → Run anyway**
3. Follow the installer wizard
4. Koda launches automatically when installation completes

Koda appears as a small icon in your **system tray** (bottom-right corner of your screen, near the clock). That's how you know it's running.

---

## Basic Usage

### Dictation — type by speaking

| Action | What to do |
|--------|-----------|
| Start recording | Hold **Ctrl + Space** |
| Speak | Talk naturally while holding |
| Paste transcription | Release **Ctrl + Space** |

Your words appear in whatever app or field was active when you pressed the hotkey.

**Tips:**
- Speak at a normal pace — no need to slow down
- Works in emails, Slack, Word, Excel, browsers, chat apps — anything
- A quiet room gives better accuracy than a great microphone
- Built-in laptop mic works fine. A USB headset is better.

---

## Other Hotkeys

| Hotkey | What it does |
|--------|-------------|
| **Ctrl + Space** | Hold to dictate, release to paste |
| **Ctrl + F9** | Prompt Assist — speak an idea, get a structured prompt ready to paste into ChatGPT or Claude. In Excel or Google Sheets, activates Formula Mode instead (see below) |
| **F7** | Correction — re-transcribes your last recording if it came out wrong |
| **F6** | Read back — Koda reads your last transcription aloud |

---

## System Tray Menu

Right-click the Koda tray icon for options:

- **Settings** — change hotkeys, microphone, model quality, and more
- **History** — see your recent transcriptions
- **Pause / Resume** — temporarily disable Koda
- **Quit** — close Koda

---

## Settings

Open Settings by right-clicking the tray icon → **Settings**.

| Setting | What it does |
|---------|-------------|
| Hotkey mode | **Hold** (default) — hold key while speaking. **Toggle** — press once to start, again to stop |
| Model quality | **Fast** (tiny), **Balanced** (base, default), **Accurate** (small) |
| Microphone | Choose which mic Koda listens to |
| Remove filler words | Automatically removes "um", "uh", "like" from transcriptions |
| Sound effects | Audio cues when recording starts and stops |

---

## Microphone Tips

You don't need an expensive mic. Here's what to expect:

| Microphone | Quality | Notes |
|-----------|---------|-------|
| Built-in laptop mic | Good | Works well in a quiet room |
| USB headset / earbuds | Better | Recommended (~$20–40) |
| Dedicated USB mic | Best | Blue Yeti, HyperX (~$60–100) |

**The biggest factor is a quiet environment** — background noise matters more than mic quality.

Make sure your microphone is set as the **default recording device** in Windows:
> Right-click the speaker icon → Sound settings → Choose your input device

---

## Formula Mode (Excel & Google Sheets)

Koda automatically detects when Excel or Google Sheets is your active window. No setup or toggle needed — just press **Ctrl + F9** and describe the formula you want.

### How to use it

1. **Click the cell** where you want the formula
2. **Hold Ctrl + F9** and speak your formula description
3. **Release** — Koda types the formula directly into the cell

That's it. You never need to know the exact formula syntax.

### What you can say

**Adding up numbers**

| What you say | What Koda types |
|---|---|
| sum B2 to B10 | `=SUM(B2:B10)` |
| sum column C | `=SUM(C:C)` |
| total of A1 to A20 | `=SUM(A1:A20)` |
| what's the sum of column B | `=SUM(B:B)` |

**Averages, max, min**

| What you say | What Koda types |
|---|---|
| average of column B | `=AVERAGE(B:B)` |
| average A1 to A20 | `=AVERAGE(A1:A20)` |
| maximum value in B2 to B10 | `=MAX(B2:B10)` |
| top of column C | `=MAX(C:C)` |
| minimum of A1 to A10 | `=MIN(A1:A10)` |

**Counting**

| What you say | What Koda types |
|---|---|
| count B2 to B10 | `=COUNT(B2:B10)` |
| how many items in column A | `=COUNT(A:A)` |
| count non-empty cells in column C | `=COUNTA(C:C)` |

**Today's date**

| What you say | What Koda types |
|---|---|
| today | `=TODAY()` |
| today's date | `=TODAY()` |

**IF statements — "if this, then that"**

| What you say | What Koda types |
|---|---|
| if A1 is greater than 10 then yes else no | `=IF(A1>10,"yes","no")` |
| if B1 is more than 100 then high else low | `=IF(B1>100,"high","low")` |
| if C1 is less than 50 then below target | `=IF(C1<50,"below target","")` |
| if A1 equals done then complete else pending | `=IF(A1="done","complete","pending")` |
| if B2 is at least 1000 then yes else no | `=IF(B2>=1000,"yes","no")` |

Words like *more than, bigger than, above, over* all mean `>`. Words like *at least, no less than* mean `>=`. You don't need to remember which symbol — just say it naturally.

**VLOOKUP — looking up a value in a table**

| What you say | What Koda types |
|---|---|
| vlookup A1 in B1 to D10 column 2 | `=VLOOKUP(A1,B1:D10,2,0)` |

### Tips

- **Whole columns work** — say "column C" instead of a range like C1:C100
- **No Excel knowledge needed** — describe what you want in plain English
- **Regular dictation still works** — if Koda doesn't recognize a formula pattern, it pastes your words as normal text, so nothing is lost
- **Ctrl + Space in Excel = plain dictation** — use this when you want to type notes or text, not formulas

### For complex formulas

If you need nested formulas or advanced logic, install [Ollama](https://ollama.com) (free, runs locally) and enable **LLM Polish** in Settings → Advanced. Run `ollama pull phi3:mini` once to set it up. Koda will use the AI model to handle anything its built-in parser can't.

---

## Troubleshooting

**Koda isn't pasting anything**
- Make sure you're clicking into the text field first before pressing the hotkey
- Check the tray icon is green (running), not paused

**Hotkeys stopped working**
- Right-click tray icon → Quit, then relaunch Koda
- This is rare — Koda automatically recovers from most hotkey issues

**Transcription is inaccurate**
- Try the **Accurate** model in Settings (slower but more precise)
- Reduce background noise
- Speak closer to the mic

**"No microphone detected"**
- Plug in your mic before launching Koda
- Set it as the default recording device in Windows Sound Settings

---

## Uninstalling

Go to **Windows Settings → Apps → Installed apps**, find **Koda**, and click **Uninstall**.

---

## Need Help?

Contact: alex@kodaspeak.com
