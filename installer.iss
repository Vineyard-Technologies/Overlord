; Overlord Inno Setup Script
[Setup]
AppName=Overlord
; AppVersion will be replaced by GitHub Actions to match the release tag
AppVersion=__APP_VERSION__
DefaultDirName={autopf}\Overlord
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
DefaultGroupName=Overlord
OutputDir=dist
; OutputBaseFilename will be replaced by GitHub Actions to include the version in the format OverlordInstallerX-X-X
OutputBaseFilename=OverlordInstaller__APP_VERSION_DASHED__
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

SetupIconFile=images\favicon.ico
VersionInfoVersion=__APP_VERSION__
VersionInfoDescription=Overlord - Render Pipeline Manager

[Files]
Source: "dist\overlord.exe"; DestDir: "{app}"; Flags: ignoreversion 64bit
Source: "scripts\masterRenderer.dsa"; DestDir: "{app}\scripts"; Flags: ignoreversion 64bit
Source: "templates\masterTemplate.duf"; DestDir: "{userappdata}\Overlord\templates"; Flags: ignoreversion
Source: "src\runIrayServer.vbs"; DestDir: "{app}\src"; Flags: ignoreversion

[Icons]

Name: "{group}\Overlord"; Filename: "{app}\overlord.exe"; Tasks: startmenuicon
Name: "{userdesktop}\Overlord"; Filename: "{app}\overlord.exe"; Tasks: desktopicon
; Ask user if they want desktop/start menu shortcuts
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Run]
Filename: "{cmd}"; Parameters: '/C pip install psutil'; StatusMsg: "Installing Python dependency: psutil..."; Flags: runhidden
Filename: "{app}\overlord.exe"; Description: "Launch Overlord"; Flags: nowait postinstall skipifsilent
