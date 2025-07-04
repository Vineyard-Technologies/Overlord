; Overlord Inno Setup Script
[Setup]
AppName=Overlord
; AppVersion will be replaced by GitHub Actions to match the release tag
AppVersion=__APP_VERSION__
DefaultDirName={pf}\Overlord
DefaultGroupName=Overlord
OutputDir=dist
; OutputBaseFilename will be replaced by GitHub Actions to include the version in the format OverlordInstallerX-X-X
OutputBaseFilename=OverlordInstaller__APP_VERSION_DASHED__
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

SetupIconFile=assets\favicon.ico
VersionInfoVersion=__APP_VERSION__
VersionInfoDescription=Overlord - Render Pipeline Manager

[Files]
Source: "dist\overlord.exe"; DestDir: "{app}"; Flags: ignoreversion 64bit
Source: "scripts\masterRenderer.dsa"; DestDir: "{app}\scripts"; Flags: ignoreversion 64bit
Source: "scripts\archiveFiles.py"; DestDir: "{app}\scripts"; Flags: ignoreversion 64bit

[Icons]
Name: "{group}\Overlord"; Filename: "{app}\overlord.exe"

[Run]
Filename: "{app}\overlord.exe"; Description: "Launch Overlord"; Flags: nowait postinstall skipifsilent
