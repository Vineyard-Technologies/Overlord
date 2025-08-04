Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the LocalAppData\Overlord directory for working directory
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
workingDir = localAppData & "\Overlord"

' Create the working directory if it doesn't exist
If Not fso.FolderExists(workingDir) Then
    fso.CreateFolder(workingDir)
End If

' Change to the working directory
WshShell.CurrentDirectory = workingDir

' Run Iray Server
cmd = """C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"""
cmd = cmd & " --install-path ""C:\Program Files\NVIDIA Corporation\Iray Server"""
WshShell.Run cmd, 0, False

Set fso = Nothing
Set WshShell = Nothing