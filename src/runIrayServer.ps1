$exe = "C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
$arguments = '--install-path "C:\Program Files\NVIDIA Corporation\Iray Server" --start-queue'

Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -PassThru