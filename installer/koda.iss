; Koda Installer — Inno Setup Script
; Packages Koda.exe into a proper Windows installer with:
;   - Start menu shortcut
;   - Desktop shortcut (optional)
;   - Auto-start on login (optional)
;   - Uninstaller
;
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" koda.iss
; Requires: Inno Setup 6 — https://jrsoftware.org/isdl.php

#define MyAppName "Koda"
#define MyAppVersion "4.2.0"
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
PrivilegesRequired=lowest
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
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
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

; Auto-start (optional)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill Koda before uninstall
Filename: "taskkill"; Parameters: "/f /im {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillKoda"

[UninstallDelete]
; Clean up runtime files
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\debug.log"
Type: files; Name: "{app}\koda_history.db"
Type: dirifempty; Name: "{app}\plugins"
Type: dirifempty; Name: "{app}\sounds"
Type: dirifempty; Name: "{app}"
