; Inno Setup script for Paperhand Beat Manager.
; Build:  ISCC.exe packaging\installer.iss   (after the PyInstaller build)
; Produces packaging\Output\PaperhandsBeatTools-Setup-<version>.exe

#define MyAppName "Paperhand Beat Manager"
#define MyAppExeName "PaperhandsBeatTools.exe"
; Version is passed in by build.ps1 (ISCC /DMyAppVersion=...) from app/version.py,
; the single source of truth. The fallback only applies if ISCC is run by hand.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Paperhand"
#define MyAppURL "https://github.com/papioshu/paperhands-beat-tools"

[Setup]
AppId={{B3F1B6E2-9C4A-4E7D-8A1F-2C9D5E7A1B34}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
; Default to Program Files, but the wizard lets the user choose another folder.
DefaultDirName={autopf}\PaperhandsBeatTools
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=PaperhandsBeatTools-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; The whole PyInstaller onedir bundle (exe + _internal + ffmpeg).
Source: "..\dist\PaperhandsBeatTools\*"; DestDir: "{app}"; \
    Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent
