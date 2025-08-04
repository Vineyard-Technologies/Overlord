Set WshShell = CreateObject("WScript.Shell")
cmd = """C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"""
cmd = cmd & " --install-path ""C:\Program Files\NVIDIA Corporation\Iray Server"""
WshShell.Run cmd, 0, False
Set WshShell = Nothing