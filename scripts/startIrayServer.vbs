' VBScript to start Iray Server (Silent Mode)

Option Explicit

Dim objShell, objFSO
Dim irayServerExe, irayInstallPath, workingDir, cmd
Dim irayServerDir, overlordDir

' Initialize objects
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Working directory - use LocalAppData\Overlord\IrayServer
overlordDir = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Overlord"
irayServerDir = overlordDir & "\IrayServer"
workingDir = irayServerDir

' Step 1: Create IrayServer directory if it doesn't exist
If Not objFSO.FolderExists(irayServerDir) Then
    On Error Resume Next
    ' Create parent Overlord directory if it doesn't exist
    If Not objFSO.FolderExists(overlordDir) Then
        objFSO.CreateFolder(overlordDir)
    End If
    ' Create IrayServer directory
    objFSO.CreateFolder(irayServerDir)
    On Error GoTo 0
End If

' Step 2: Start Iray Server

' Iray Server paths
irayServerExe = "C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
irayInstallPath = "C:\Program Files\NVIDIA Corporation\Iray Server"

' Check if Iray Server executable exists
If Not objFSO.FileExists(irayServerExe) Then
    WScript.Quit 1
End If

' Build command
cmd = """" & irayServerExe & """ --install-path """ & irayInstallPath & """ --start-queue"

' Start Iray Server
On Error Resume Next
objShell.CurrentDirectory = workingDir
objShell.Run cmd, 0, False  ' 0 = hide window, False = don't wait
If Err.Number = 0 Then
Else
End If
On Error GoTo 0

' Clean up objects
Set objShell = Nothing
Set objFSO = Nothing