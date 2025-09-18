' VBScript to start Iray Server
' Minimal version - just starts the server

Option Explicit

Dim objShell, objFSO
Dim irayServerExe, irayInstallPath, workingDir, cmd

' Initialize objects
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Iray Server paths
irayServerExe = "C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
irayInstallPath = "C:\Program Files\NVIDIA Corporation\Iray Server"

' Working directory - use LocalAppData\Overlord
workingDir = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Overlord"

' Create working directory if it doesn't exist
If Not objFSO.FolderExists(workingDir) Then
    On Error Resume Next
    objFSO.CreateFolder(workingDir)
    On Error GoTo 0
End If

' Build command
cmd = """" & irayServerExe & """ --install-path """ & irayInstallPath & """ --start-queue"

' Start Iray Server
On Error Resume Next
objShell.CurrentDirectory = workingDir
objShell.Run cmd, 0, False  ' 0 = hide window, False = don't wait
On Error GoTo 0

' Clean up objects
Set objShell = Nothing
Set objFSO = Nothing
