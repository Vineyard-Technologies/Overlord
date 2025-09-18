Option Explicit
Dim objWMIService, colProcesses, objProcess, i
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
For i = 0 To 1
    Set colProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE Name = '" & Array("iray_server.exe", "iray_server_worker.exe")(i) & "'")
    For Each objProcess In colProcesses
        On Error Resume Next
        objProcess.Terminate()
        On Error GoTo 0
    Next
Next
