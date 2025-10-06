' VBScript to restart Iray Server (Silent Mode)
' Combines kill, cache cleanup, and start operations

Option Explicit

Dim objWMIService, colProcesses, objProcess, i
Dim objShell, objFSO
Dim irayServerExe, irayInstallPath, workingDir, cmd
Dim irayServerDir, overlordDir

' Initialize objects
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")

' Working directory - use LocalAppData\Overlord\IrayServer
overlordDir = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Overlord"
irayServerDir = overlordDir & "\IrayServer"
workingDir = irayServerDir

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

' Step 2: Delete entire IrayServer folder if it exists
If objFSO.FolderExists(irayServerDir) Then
    ' Retry loop for folder deletion (in case files are still locked)
    Dim retryCount, maxRetries
    retryCount = 0
    maxRetries = 10
    
    Do While objFSO.FolderExists(irayServerDir) And retryCount < maxRetries
        On Error Resume Next
        objFSO.DeleteFolder irayServerDir, True
        If Err.Number <> 0 Then
            WScript.Sleep 1000
            retryCount = retryCount + 1
            Err.Clear
        Else
            Exit Do
        End If
        On Error GoTo 0
    Loop
End If

' Step 3: Create IrayServer directory
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

' Step 4: Start Iray Server

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
Set objWMIService = Nothing
Set colProcesses = Nothing