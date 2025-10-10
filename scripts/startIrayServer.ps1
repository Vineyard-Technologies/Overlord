# PowerShell script to start Iray Server (Silent Mode)

# Set error action preference to stop on errors
$ErrorActionPreference = "SilentlyContinue"

# Working directory - use LocalAppData\Overlord\IrayServer
$overlordDir = Join-Path $env:LOCALAPPDATA "Overlord"
$irayServerDir = Join-Path $overlordDir "IrayServer"
$workingDir = $irayServerDir

# Step 1: Create IrayServer directory if it doesn't exist
try {
    if (-not (Test-Path $irayServerDir)) {
        # Create parent Overlord directory if it doesn't exist
        if (-not (Test-Path $overlordDir)) {
            New-Item -Path $overlordDir -ItemType Directory -Force | Out-Null
        }
        # Create IrayServer directory
        New-Item -Path $irayServerDir -ItemType Directory -Force | Out-Null
    }
} catch {
    # Ignore directory creation errors
}

# Step 2: Start Iray Server

# Iray Server paths
$irayServerExe = "C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
$irayInstallPath = "C:\Program Files\NVIDIA Corporation\Iray Server"

# Check if Iray Server executable exists
if (-not (Test-Path $irayServerExe)) {
    exit 1
}

# Build arguments array for Start-Process
$arguments = @(
    "--install-path", 
    "`"$irayInstallPath`"",
    "--start-queue"
)

# Start Iray Server
try {
    Set-Location $workingDir
    Start-Process -FilePath $irayServerExe -ArgumentList $arguments -WindowStyle Hidden -PassThru | Out-Null
    exit 0
} catch {
    exit 1
}