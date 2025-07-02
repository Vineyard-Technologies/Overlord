; Overlord Inno Setup Script
[Setup]
AppName=Overlord
AppVersion=1.0
DefaultDirName={pf}\Overlord
DefaultGroupName=Overlord
OutputDir=dist
OutputBaseFilename=overlord-setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

SetupIconFile=assets\favicon.ico

[Files]
Source: "dist\overlord.exe"; DestDir: "{app}"; Flags: ignoreversion 64bit
Source: "scripts\masterRenderer.dsa"; DestDir: "{app}\scripts"; Flags: ignoreversion 64bit

[Icons]
Name: "{group}\Overlord"; Filename: "{app}\overlord.exe"
