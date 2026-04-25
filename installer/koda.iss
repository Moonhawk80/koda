; Koda Installer — Inno Setup Script
; Packages Koda.exe into a proper Windows installer with:
;   - Start menu shortcut
;   - Auto-start on login (optional)
;   - Custom wizard pages (mic guidance, activation, quality, formula mode)
;   - Uninstaller
;
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" koda.iss
; Requires: Inno Setup 6 — https://jrsoftware.org/isdl.php

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
{ ------------------------------------------------------------------ }
{ Custom wizard pages                                                  }
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

{ Win32 API — count audio input devices (recording devices) without }
{ needing PortAudio or any helper exe. Returns 0 when no mic is set up. }
function waveInGetNumDevs: Cardinal;
  external 'waveInGetNumDevs@winmm.dll stdcall';

procedure InitializeWizard();
var
  MicMsg: String;
  DeviceCount: Cardinal;
begin
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

procedure CurStepChanged(CurStep: TSetupStep);
var
  HotkeyMode, ModelSize: String;
  FormulaEnabled: String;
  ConfigDir, ConfigFile, ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    { Hotkey mode }
    if HotkeyPage.Values[0] then
      HotkeyMode := 'hold'
    else
      HotkeyMode := 'toggle';

    { Model size }
    if ModelPage.Values[0] then
      ModelSize := 'small'
    else if ModelPage.Values[1] then
      ModelSize := 'base'
    else
      ModelSize := 'tiny';

    { Formula mode }
    if FormulaPage.Values[0] then
      FormulaEnabled := 'true'
    else
      FormulaEnabled := 'false';

    { Write config.json to %APPDATA%\Koda\ — only on fresh install }
    ConfigDir := ExpandConstant('{userappdata}') + '\Koda';
    ForceDirectories(ConfigDir);
    ConfigFile := ConfigDir + '\config.json';

    if not FileExists(ConfigFile) then
    begin
      ConfigContent :=
        '{' + #13#10 +
        '  "hotkey_mode": "' + HotkeyMode + '",' + #13#10 +
        '  "model_size": "' + ModelSize + '",' + #13#10 +
        '  "formula_mode": {"enabled": ' + FormulaEnabled + ', "auto_detect_apps": true}' + #13#10 +
        '}';
      SaveStringToFile(ConfigFile, ConfigContent, False);
    end;
  end;
end;
