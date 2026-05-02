; Koda Installer — Inno Setup Script
; Packages Koda.exe into a proper Windows installer with:
;   - Start menu shortcut
;   - Auto-start on login (optional)
;   - Custom wizard pages (mic guidance, activation, quality, formula mode)
;   - Uninstaller
;
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" koda.iss
; Requires: Inno Setup 6 — https://jrsoftware.org/isdl.php

; Pull in tier-classification thresholds (auto-generated from
; system_check_constants.py). Defines global #define symbols consumed
; by system_check.iss inside [Code]. Must be #include'd at script top
; scope so the #define's are visible to subsequent includes.
#include "thresholds.iss"

#define MyAppName "Koda"
#define MyAppVersion "4.4.0-beta1"
#define MyAppVersionNumeric "4.4.0.1"
#define MyAppPublisher "Alex Concepcion"
#define MyAppURL "https://github.com/Moonhawk80/koda"
#define MyAppExeName "Koda.exe"
#define MyAppDescription "Push-to-talk voice transcription for Windows"
#define MyAppCopyright "Copyright 2026 Alexis Concepcion"

[Setup]
AppId={{B7E3F2A1-8C4D-4E5F-9A6B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppCopyright={#MyAppCopyright}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=KodaSetup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=wizard_banner.bmp
WizardSmallImageFile=wizard_small.bmp
LicenseFile=..\LICENSE
; admin required so desktop/startup shortcuts land in {commondesktop} / {commonstartup}
; (Public\Desktop is NOT OneDrive-synced, so shortcuts don't get the sync-status overlay)
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
SetupIconFile=..\koda.ico
UninstallDisplayIcon={app}\koda.ico
SetupLogging=yes
; Version info embedded in the installer exe
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright={#MyAppCopyright}
VersionInfoDescription={#MyAppDescription}
VersionInfoVersion={#MyAppVersionNumeric}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersionNumeric}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start Koda when Windows starts"; GroupDescription: "Startup:"

[Files]
; Main executable (built by PyInstaller)
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Config and data files (created at runtime, but ship defaults)
Source: "..\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\profiles.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\custom_words.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

; Sound effects
Source: "..\sounds\*.wav"; DestDir: "{app}\sounds"; Flags: ignoreversion

; Icon file
Source: "..\koda.ico"; DestDir: "{app}"; Flags: ignoreversion

; Plugins directory (empty by default, user adds plugins here)
Source: "..\plugins\__init__.py"; DestDir: "{app}\plugins"; Flags: ignoreversion

; Power Mode celebration assets — extracted to {tmp} on demand by the
; wizard page (not installed to {app}). dontcopy = bundled in installer
; but only materialised via ExtractTemporaryFile when needed.
Source: "power_banner.bmp"; Flags: dontcopy
Source: "..\sounds\success.wav"; Flags: dontcopy

[Dirs]
; Ensure plugins directory exists and is writable
Name: "{app}\plugins"; Permissions: users-modify

[Icons]
; Start menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\koda.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop shortcut — Public\Desktop (not OneDrive-synced, no blue-check overlay)
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\koda.ico"; Tasks: desktopicon

; Auto-start (optional)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
; Register right-click "Transcribe with Koda" context menu (silent, non-blocking)
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install-context-menu"; Flags: runhidden; StatusMsg: "Registering right-click menu..."
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill Koda before uninstall
Filename: "taskkill"; Parameters: "/f /im {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillKoda"
; Unregister right-click context menu (Koda.exe still exists in {app} at this point)
Filename: "{app}\{#MyAppExeName}"; Parameters: "--uninstall-context-menu"; Flags: runhidden; RunOnceId: "UninstallContextMenu"

[UninstallDelete]
; Clean up runtime files
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\debug.log"
Type: files; Name: "{app}\koda_history.db"
Type: dirifempty; Name: "{app}\plugins"
Type: dirifempty; Name: "{app}\sounds"
Type: dirifempty; Name: "{app}"

[Code]
#include "system_check.iss"

{ ------------------------------------------------------------------ }
{ Custom wizard pages                                                  }
{   Tier pages — BLOCKED hard-stop / MINIMUM soft-warn (conditional)  }
{   Page 1 — Microphone guidance (informational)                      }
{   Page 2 — Activation method: Hold vs Toggle                        }
{   Page 3 — Transcription quality (small / base / tiny)              }
{   Page 4 — Formula mode for Excel / Google Sheets                   }
{ ------------------------------------------------------------------ }

var
  MicPage:       TOutputMsgWizardPage;
  HotkeyPage:    TInputOptionWizardPage;
  ModelPage:     TInputOptionWizardPage;
  FormulaPage:   TInputOptionWizardPage;
  { Tier-classification pages — created conditionally in InitializeWizard }
  BlockedPage:           TOutputMsgWizardPage;
  MinimumPage:           TOutputMsgWizardPage;
  PowerPage:             TWizardPage;
  PowerPageContinueRadio: TNewRadioButton;
  DetectedTier:          String;

{ Win32 API — count audio input devices (recording devices) without }
{ needing PortAudio or any helper exe. Returns 0 when no mic is set up. }
function waveInGetNumDevs: Cardinal;
  external 'waveInGetNumDevs@winmm.dll stdcall';

{ Win32 API — fire-and-forget audio playback for the Power Mode banner.
  mciSendStringW is the Unicode entrypoint, matching modern Inno's
  Unicode-only PascalScript strings. Passing a null-cast Integer for
  hwndCallback (we never want a notification posted back). }
function mciSendString(lpszCommand, lpszReturnString: String;
                       cchReturn, hwndCallback: Cardinal): Cardinal;
  external 'mciSendStringW@winmm.dll stdcall';

(* Read the GPU name written by system_check.iss:DetectNvidiaGpuPresent
   into the wizard temp dir's nvidia_check.txt file. Returns "NVIDIA GPU"
   when the file is missing or empty (defensive — the celebration page
   should still render even if the nvidia-smi probe got cleaned up). *)
function GetNvidiaGpuNameForDisplay: String;
var
  TempPath: String;
  Lines: TStringList;
begin
  Result := 'NVIDIA GPU';
  TempPath := ExpandConstant('{tmp}\nvidia_check.txt');
  if not FileExists(TempPath) then Exit;
  Lines := TStringList.Create;
  try
    Lines.LoadFromFile(TempPath);
    if (Lines.Count > 0) and (Trim(Lines[0]) <> '') then
      Result := Trim(Lines[0]);
  finally
    Lines.Free;
  end;
end;

{ Play sounds/success.wav once. Called from CurPageChanged when the
  Power Mode page activates — NOT from CreatePowerPageContent (which
  runs at wizard init, far before the user reaches the page). }
procedure PlayPowerModeSound;
var
  WavPath: String;
begin
  ExtractTemporaryFile('success.wav');
  WavPath := ExpandConstant('{tmp}\success.wav');
  { Close any prior alias before reopening; ignore failures. }
  mciSendString('close kodasuccess', '', 0, 0);
  mciSendString('open "' + WavPath + '" alias kodasuccess', '', 0, 0);
  mciSendString('play kodasuccess', '', 0, 0);
end;

{ Compose the Power Mode celebration page — banner bitmap + GPU name
  label + body copy + Continue/Standard radio choice. Called once from
  InitializeWizard when DetectedTier = 'POWER'. }
procedure CreatePowerPageContent(Page: TWizardPage);
var
  Banner: TBitmapImage;
  GpuLabel, BodyLabel: TNewStaticText;
  StandardRadio: TNewRadioButton;
begin
  ExtractTemporaryFile('power_banner.bmp');

  Banner := TBitmapImage.Create(Page);
  Banner.Parent := Page.Surface;
  Banner.Left := (Page.SurfaceWidth - 600) div 2;
  Banner.Top := 0;
  Banner.Width := 600;
  Banner.Height := 300;
  Banner.Bitmap.LoadFromFile(ExpandConstant('{tmp}\power_banner.bmp'));

  BodyLabel := TNewStaticText.Create(Page);
  BodyLabel.Parent := Page.Surface;
  BodyLabel.Caption := 'Near-instant transcription. Larger, more accurate model.';
  BodyLabel.Left := 0;
  BodyLabel.Top := 312;
  BodyLabel.Width := Page.SurfaceWidth;
  BodyLabel.AutoSize := False;
  BodyLabel.Font.Style := [fsBold];

  GpuLabel := TNewStaticText.Create(Page);
  GpuLabel.Parent := Page.Surface;
  GpuLabel.Caption := 'Detected: ' + GetNvidiaGpuNameForDisplay;
  GpuLabel.Left := 0;
  GpuLabel.Top := 334;
  GpuLabel.Width := Page.SurfaceWidth;

  PowerPageContinueRadio := TNewRadioButton.Create(Page);
  PowerPageContinueRadio.Parent := Page.Surface;
  PowerPageContinueRadio.Caption := 'Continue with Power Mode';
  PowerPageContinueRadio.Top := 372;
  PowerPageContinueRadio.Width := Page.SurfaceWidth;
  PowerPageContinueRadio.Checked := True;

  StandardRadio := TNewRadioButton.Create(Page);
  StandardRadio.Parent := Page.Surface;
  StandardRadio.Caption := 'Use Standard Mode instead';
  StandardRadio.Top := 397;
  StandardRadio.Width := Page.SurfaceWidth;
end;

procedure InitializeWizard();
var
  MicMsg: String;
  DeviceCount: Cardinal;
begin
  { Classify hardware first — pages added below depend on tier }
  DetectedTier := ClassifyTier;

  { BLOCKED — hard-stop page; user must Cancel (forward nav blocked below) }
  if DetectedTier = 'BLOCKED' then
  begin
    BlockedPage := CreateOutputMsgPage(
      wpWelcome,
      'System Requirements Not Met',
      'Your PC does not meet the minimum requirements for Koda.',
      'Koda needs:' + #13#10 +
      '  - At least 2 GB of RAM' + #13#10 +
      '  - At least 4 GB of free disk space' + #13#10 +
      '  - Windows 10 (May 2020 update) or later' + #13#10 + #13#10 +
      'Setup will close. Please upgrade your hardware or operating ' +
      'system and try again.'
    );
  end;

  { MINIMUM — soft-warn page; user can continue }
  if DetectedTier = 'MINIMUM' then
  begin
    MinimumPage := CreateOutputMsgPage(
      wpWelcome,
      'Below Recommended Specs',
      'Koda will work, but transcription will be slower than typical.',
      'Your PC is below the recommended specs for Koda.' + #13#10 + #13#10 +
      'Koda will configure itself for the best experience your PC can ' +
      'deliver. Estimated transcription time: 12-25 seconds for a ' +
      '60-second clip.' + #13#10 + #13#10 +
      'You can change these settings later in Koda > Settings > ' +
      'Performance.'
    );
  end;

  { POWER — celebratory wizard page (banner + GPU label + radio choice) }
  if DetectedTier = 'POWER' then
  begin
    PowerPage := CreateCustomPage(
      wpWelcome,
      'Power Mode Available',
      'Your hardware just unlocked Koda''s fastest mode.'
    );
    CreatePowerPageContent(PowerPage);
  end;

  { PAGE 1 — Microphone guidance }
  DeviceCount := waveInGetNumDevs();

  MicMsg := '';
  if DeviceCount = 0 then
    MicMsg :=
      '*** NO MICROPHONE DETECTED ***' + #13#10 + #13#10 +
      'Windows is not reporting any recording devices on this PC.' + #13#10 +
      'Koda needs a microphone to work.' + #13#10 + #13#10 +
      'Before Koda can transcribe:' + #13#10 +
      '  1. Plug in a microphone, headset, or webcam with a mic' + #13#10 +
      '  2. Right-click the speaker icon in the taskbar' + #13#10 +
      '     -> Sound settings -> Input -> pick your mic as the default' + #13#10 +
      '  3. Confirm the input level bar moves when you speak' + #13#10 + #13#10 +
      'Installation will continue, but Koda will sit idle with a' + #13#10 +
      '"Mic error" tray icon until a microphone is set up.' + #13#10 +
      'Once you plug one in, Koda recovers automatically (no restart).' + #13#10 + #13#10 +
      '--- General microphone guidance ---' + #13#10 + #13#10;

  MicMsg := MicMsg +
    'Koda will use your Windows default microphone.' + #13#10 +
    'You can change this in Settings after installation.' + #13#10 + #13#10 +
    'What to expect with different microphones:' + #13#10 + #13#10 +
    '  Built-in laptop microphone' + #13#10 +
    '    Works well. Background noise may reduce accuracy.' + #13#10 +
    '    Best results in a quiet room.' + #13#10 + #13#10 +
    '  USB headset / earbuds' + #13#10 +
    '    Good quality. Affordable ($15-40).' + #13#10 + #13#10 +
    '  Dedicated USB microphone' + #13#10 +
    '    Best accuracy. ($50-100, e.g. Blue Yeti, HyperX SoloCast)' + #13#10 + #13#10 +
    'Tip: A quiet environment matters more than mic quality.' + #13#10 + #13#10 +
    'Make sure your mic is set as the default recording device' + #13#10 +
    'in Windows Sound Settings (right-click speaker icon → Sound settings).';

  MicPage := CreateOutputMsgPage(
    wpSelectTasks,
    'Your Microphone',
    'Koda works with any Windows microphone.',
    MicMsg
  );

  { PAGE 2 — Activation method }
  HotkeyPage := CreateInputOptionPage(
    MicPage.ID,
    'Activation Method',
    'How would you like to start voice input?',
    'Choose how you use Ctrl+Space to dictate:',
    True,   { exclusive — radio buttons }
    False   { not a list box }
  );
  HotkeyPage.Add('Hold to talk  (Recommended)');
  HotkeyPage.Add('Toggle on/off');
  HotkeyPage.Values[0] := True;  { default: Hold }

  { PAGE 3 — Transcription quality }
  ModelPage := CreateInputOptionPage(
    HotkeyPage.ID,
    'Transcription Quality',
    'How accurate should speech recognition be?',
    'Choose your transcription quality (can be changed later in Settings):',
    True,
    False
  );
  ModelPage.Add('Accurate  (Recommended) — Built-in model, works without internet');
  ModelPage.Add('Balanced — Downloads ~150 MB on first launch');
  ModelPage.Add('Fast — Downloads ~75 MB on first launch, lower accuracy');
  ModelPage.Values[0] := True;  { default: Accurate / small — the bundled model }

  { PAGE 4 — Formula mode }
  FormulaPage := CreateInputOptionPage(
    ModelPage.ID,
    'Formula Assistant',
    'Speak Excel and Google Sheets formulas naturally.',
    'Enable formula mode?',
    True,
    False
  );
  FormulaPage.Add('Enable formula mode');
  FormulaPage.Add('Disable (I don''t use Excel or Google Sheets)');
  FormulaPage.Values[1] := True;  { default: disabled — user opts in }
end;

{ Minimal JSON extractor — only reads the top-level "tier" string field.
  Avoids pulling in a full JSON parser. PascalScript-safe: uses a large
  literal length instead of MaxInt, and Copy() is 1-indexed. }
function ExtractTierFromJson(const JsonText: String): String;
var
  TierIdx, ColonIdx, OpenQuoteIdx, CloseQuoteIdx: Integer;
  AfterTier, AfterColon, AfterOpenQuote: String;
begin
  Result := 'RECOMMENDED';  { fail-safe default }
  TierIdx := Pos('"tier"', JsonText);
  if TierIdx = 0 then Exit;

  { Slice from "tier" to end of string and find the colon. }
  AfterTier := Copy(JsonText, TierIdx, 1000000);
  ColonIdx := Pos(':', AfterTier);
  if ColonIdx = 0 then Exit;

  { Slice past the colon and find the opening quote of the value. }
  AfterColon := Copy(JsonText, TierIdx + ColonIdx, 1000000);
  OpenQuoteIdx := Pos('"', AfterColon);
  if OpenQuoteIdx = 0 then Exit;

  { Slice past the opening quote and find the closing quote. }
  AfterOpenQuote := Copy(JsonText, TierIdx + ColonIdx + OpenQuoteIdx, 1000000);
  CloseQuoteIdx := Pos('"', AfterOpenQuote);
  if CloseQuoteIdx = 0 then Exit;

  { CloseQuoteIdx is the 1-indexed position of the closing quote within
    AfterOpenQuote, so the value length is CloseQuoteIdx - 1. }
  Result := Copy(JsonText,
                 TierIdx + ColonIdx + OpenQuoteIdx,
                 CloseQuoteIdx - 1);
end;

{ Build the tier-aware config.json string. Tier dictates cpu_threads and
  process_priority; ModelSize is decided by the caller (POWER/MINIMUM
  override the wizard pick, RECOMMENDED honors it). }
function BuildTierAwareConfigJson(
  const Tier, HotkeyMode, ModelSize, FormulaEnabled: String
): String;
var
  CpuThreads, ProcessPriority: String;
begin
  { PascalScript `case` does not support String selectors — use if/elseif. }
  if Tier = 'POWER' then
  begin
    CpuThreads := '4';
    ProcessPriority := 'above_normal';
  end
  else if Tier = 'MINIMUM' then
  begin
    CpuThreads := '2';
    ProcessPriority := 'normal';
  end
  else
  begin
    { RECOMMENDED or fallback }
    CpuThreads := '4';
    ProcessPriority := 'above_normal';
  end;

  Result :=
    '{' + #13#10 +
    '  "hotkey_mode": "' + HotkeyMode + '",' + #13#10 +
    '  "model_size": "' + ModelSize + '",' + #13#10 +
    '  "cpu_threads": ' + CpuThreads + ',' + #13#10 +
    '  "process_priority": "' + ProcessPriority + '",' + #13#10 +
    '  "system_check_tier": "' + Tier + '",' + #13#10 +
    '  "system_check_mode": "auto-detect",' + #13#10 +
    '  "formula_mode": {"enabled": ' + FormulaEnabled +
                       ', "auto_detect_apps": true}' + #13#10 +
    '}';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  HotkeyMode, ModelSize: String;
  FormulaEnabled: String;
  ConfigDir, ConfigFile, ConfigContent: String;
  TempJsonPath: String;
  JsonText: AnsiString;  { LoadStringFromFile requires AnsiString in Unicode Inno }
  ResultCode: Integer;
  KodaExePath: String;
  TierFromJson: String;
begin
  if CurStep = ssPostInstall then
  begin
    { Run the just-installed Koda.exe to get authoritative classification.
      The CLI flag is provided by the --detect-hardware --json command. }
    KodaExePath := ExpandConstant('{app}\Koda.exe');
    TempJsonPath := ExpandConstant('{tmp}\hwdetect.json');
    TierFromJson := '';

    if FileExists(KodaExePath) then
    begin
      Exec(
        ExpandConstant('{cmd}'),
        '/c ""' + KodaExePath + '" --detect-hardware --json > "' + TempJsonPath + '""',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode
      );
      if ResultCode <> 0 then
        Log('Koda.exe --detect-hardware exited with code ' + IntToStr(ResultCode) +
            '; will fall back to wizard-time tier ' + DetectedTier);
    end
    else
      Log('Koda.exe not found at ' + KodaExePath +
          '; falling back to wizard-time tier ' + DetectedTier);

    { Parse the tier from JSON (minimal extraction — we just need the "tier" field) }
    if FileExists(TempJsonPath) and LoadStringFromFile(TempJsonPath, JsonText) then
    begin
      TierFromJson := ExtractTierFromJson(String(JsonText));
    end
    else
    begin
      { Fall back to wizard-time classification if Koda.exe didn't run }
      TierFromJson := DetectedTier;
    end;

    { Honor the user's Power Mode choice — if they picked Standard Mode
      on the celebration page, downgrade tier to RECOMMENDED before the
      model-size dispatch below. The radio is only created when the
      Power page itself was shown, so a nil check is required. }
    if (PowerPageContinueRadio <> nil) and
       (not PowerPageContinueRadio.Checked) then
    begin
      TierFromJson := 'RECOMMENDED';
    end;

    { Hotkey mode }
    if HotkeyPage.Values[0] then
      HotkeyMode := 'hold'
    else
      HotkeyMode := 'toggle';

    { Model size — tier overrides the wizard pick for POWER and MINIMUM.
      RECOMMENDED (or any unrecognized fallback) honors what the user picked. }
    if TierFromJson = 'POWER' then
      ModelSize := 'large-v3-turbo'
    else if TierFromJson = 'MINIMUM' then
      ModelSize := 'tiny'
    else
    begin
      if ModelPage.Values[0] then
        ModelSize := 'small'
      else if ModelPage.Values[1] then
        ModelSize := 'base'
      else
        ModelSize := 'tiny';
    end;

    { Formula mode }
    if FormulaPage.Values[0] then
      FormulaEnabled := 'true'
    else
      FormulaEnabled := 'false';

    { Write tier-aware config.json to %APPDATA%\Koda\ — only on fresh install }
    ConfigDir := ExpandConstant('{userappdata}') + '\Koda';
    ForceDirectories(ConfigDir);
    ConfigFile := ConfigDir + '\config.json';

    if not FileExists(ConfigFile) then
    begin
      ConfigContent := BuildTierAwareConfigJson(
        TierFromJson, HotkeyMode, ModelSize, FormulaEnabled
      );
      SaveStringToFile(ConfigFile, ConfigContent, False);
    end;
  end;
end;

{ Play the success cue when the Power Mode page activates. }
procedure CurPageChanged(CurPageID: Integer);
begin
  if (PowerPage <> nil) and (CurPageID = PowerPage.ID) then
    PlayPowerModeSound;
end;

{ Skip every page after the BLOCKED page so the user has nowhere to go but Cancel. }
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if DetectedTier = 'BLOCKED' then
  begin
    if (BlockedPage <> nil) and (PageID > BlockedPage.ID) then
      Result := True;
  end;
end;

{ Block forward navigation while the user is on the BLOCKED page. }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (DetectedTier = 'BLOCKED') and (BlockedPage <> nil) and
     (CurPageID = BlockedPage.ID) then
  begin
    MsgBox('Setup cannot continue on this PC. Please cancel.', mbError, MB_OK);
    Result := False;
  end;
end;
