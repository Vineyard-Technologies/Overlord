' VBScript to kill Iray Server processes
' Equivalent functionality to Overlord.py's stop_iray_server() function

Option Explicit

Dim objWMIService, colProcesses, objProcess
Dim processesToKill, processName
Dim killedCount, i

' Array of process names to kill (equivalent to IRAY_SERVER_PROCESSES in Python)
processesToKill = Array("iray_server.exe", "iray_server_worker.exe")
killedCount = 0

' Connect to WMI service
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")

' Loop through each process type we want to kill
For i = 0 To UBound(processesToKill)
    processName = processesToKill(i)
    
    ' Query for processes with the specified name
    Set colProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE Name = '" & processName & "'")
    
    ' Kill each matching process
    For Each objProcess In colProcesses
        On Error Resume Next
        objProcess.Terminate()
        If Err.Number = 0 Then
            WScript.Echo "Killed process: " & processName & " (PID: " & objProcess.ProcessId & ")"
            killedCount = killedCount + 1
        Else
            WScript.Echo "Failed to kill process: " & processName & " (PID: " & objProcess.ProcessId & ") - Error: " & Err.Description
        End If
        On Error GoTo 0
    Next
Next

' Report results
If killedCount > 0 Then
    WScript.Echo "Successfully killed " & killedCount & " Iray Server process(es)"
Else
    WScript.Echo "No Iray Server processes found to kill"
End If

' Clean up objects
Set objProcess = Nothing
Set colProcesses = Nothing
Set objWMIService = Nothing

WScript.Echo "Iray Server kill script completed"
