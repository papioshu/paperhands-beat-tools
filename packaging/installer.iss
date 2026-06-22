; Inno Setup script for Paperhand's Beat Tools.
; Build:  ISCC.exe packaging\installer.iss   (after the PyInstaller build)
; Produces packaging\Output\PaperhandsBeatTools-Setup-<version>.exe

#define MyAppName "Paperhand's Beat Tools"
#define MyAppExeName "PaperhandsBeatTools.exe"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "papioshu"
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
