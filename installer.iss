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

[Files]
Source: "dist\overlord.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Overlord"; Filename: "{app}\overlord.exe"
