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

' Working directory - use LocalAppData\Overlord
workingDir = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Overlord"
cacheDir = workingDir & "\cache"
cacheDbPath = cacheDir & "\cache.db"

' Create working directory if it doesn't exist
If Not objFSO.FolderExists(workingDir) Then
    On Error Resume Next
    objFSO.CreateFolder(workingDir)
    On Error GoTo 0
End If

' Create cache directory if it doesn't exist
If Not objFSO.FolderExists(cacheDir) Then
    On Error Resume Next
    objFSO.CreateFolder(cacheDir)
    On Error GoTo 0
End If

' Step 1: Kill Iray Server processes
' WScript.Echo "Killing Iray Server processes..."
For i = 0 To 1
    Set colProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE Name = '" & Array("iray_server.exe", "iray_server_worker.exe")(i) & "'")
    For Each objProcess In colProcesses
        On Error Resume Next
        objProcess.Terminate()
        ' WScript.Echo "Terminated process: " & objProcess.Name & " (PID: " & objProcess.ProcessId & ")"
        On Error GoTo 0
    Next
Next

' Wait a moment for processes to fully terminate
WScript.Sleep 2000

' Step 2: Delete cache.db if it exists
If objFSO.FileExists(cacheDbPath) Then
    ' WScript.Echo "Cache database exists at: " & cacheDbPath
    ' WScript.Echo "Removing cache database..."
    
    ' Retry loop for cache deletion (in case file is still locked)
    Dim retryCount, maxRetries
    retryCount = 0
    maxRetries = 10
    
    Do While objFSO.FileExists(cacheDbPath) And retryCount < maxRetries
        On Error Resume Next
        objFSO.DeleteFile cacheDbPath, True
        If Err.Number <> 0 Then
            ' WScript.Echo "Failed to remove cache.db (attempt " & (retryCount + 1) & "/" & maxRetries & "), retrying..."
            WScript.Sleep 1000
            retryCount = retryCount + 1
            Err.Clear
        Else
            ' WScript.Echo "Successfully removed cache.db"
            Exit Do
        End If
        On Error GoTo 0
    Loop
    
    If objFSO.FileExists(cacheDbPath) And retryCount >= maxRetries Then
        ' WScript.Echo "Warning: Could not remove cache.db after " & maxRetries & " attempts"
    End If
Else
    ' WScript.Echo "Cache database does not exist at: " & cacheDbPath
End If

' Step 3: Start Iray Server
' WScript.Echo "Starting Iray Server..."

' Iray Server paths
irayServerExe = "C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
irayInstallPath = "C:\Program Files\NVIDIA Corporation\Iray Server"

' Check if Iray Server executable exists
If Not objFSO.FileExists(irayServerExe) Then
    ' WScript.Echo "Error: Iray Server executable not found at: " & irayServerExe
    WScript.Quit 1
End If

' Build command
cmd = """" & irayServerExe & """ --install-path """ & irayInstallPath & """ --start-queue"

' Start Iray Server
On Error Resume Next
objShell.CurrentDirectory = workingDir
' WScript.Echo "Executing: " & cmd
' WScript.Echo "Working directory: " & workingDir
objShell.Run cmd, 0, False  ' 0 = hide window, False = don't wait
If Err.Number = 0 Then
    ' WScript.Echo "Iray Server started successfully"
Else
    ' WScript.Echo "Error starting Iray Server: " & Err.Description
End If
On Error GoTo 0

' Clean up objects
Set objShell = Nothing
Set objFSO = Nothing
Set objWMIService = Nothing
Set colProcesses = Nothing

' WScript.Echo "Iray Server restart sequence completed"