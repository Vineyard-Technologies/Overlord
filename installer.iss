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

SetupIconFile=assets\favicon.ico

[Files]
Source: "dist\overlord.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\masterRenderer.dsa"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{group}\Overlord"; Filename: "{app}\overlord.exe"
