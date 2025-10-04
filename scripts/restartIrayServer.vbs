' VBScript to restart Iray Server (Silent Mode)
' Combines kill, cache cleanup, and start operations

Option Explicit

Dim objWMIService, colProcesses, objProcess, i
Dim objShell, objFSO
Dim irayServerExe, irayInstallPath, workingDir, cmd
Dim cacheDbPath, cacheDir

' Initialize objects
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")

' Working directory - use LocalAppData\Overlord\IrayServer
workingDir = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Overlord\IrayServer"

' Step 1: Kill Iray Server processes
For i = 0 To 1
    Set colProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE Name = '" & Array("iray_server.exe", "iray_server_worker.exe")(i) & "'")
    For Each objProcess In colProcesses
        On Error Resume Next
        objProcess.Terminate()
        On Error GoTo 0
    Next
Next

' Wait a moment for processes to fully terminate
WScript.Sleep 2000

' Step 2: Delete IrayServer directory
If objFSO.FolderExists(workingDir) Then
    On Error Resume Next
    objFSO.DeleteFolder workingDir, True
    On Error GoTo 0
End If

' Step 3: Start Iray Server

' Iray Server paths
irayServerExe = "C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
irayInstallPath = "C:\Program Files\NVIDIA Corporation\Iray Server"

' Check if Iray Server executable exists
If Not objFSO.FileExists(irayServerExe) Then
    WScript.Quit 1
End If

' Build command
cmd = """" & irayServerExe & """ --install-path """ & irayInstallPath & """ --start-queue"

' Create working directory for Iray Server
If Not objFSO.FolderExists(workingDir) Then
    On Error Resume Next
    objFSO.CreateFolder(objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Overlord")
    objFSO.CreateFolder(workingDir)
    On Error GoTo 0
End If

' Start Iray Server
On Error Resume Next
objShell.CurrentDirectory = workingDir
objShell.Run cmd, 0, False  ' 0 = hide window, False = don't wait
If Err.Number = 0 Then
    ' Iray Server started successfully
End If
On Error GoTo 0

' Clean up objects
Set objShell = Nothing
Set objFSO = Nothing
Set objWMIService = Nothing
Set colProcesses = Nothing