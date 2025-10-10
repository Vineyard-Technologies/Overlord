# PowerShell script to stop Iray Server processes and clean up cache (Silent Mode)

# Set error action preference to continue on errors (like VBS "On Error Resume Next")
$ErrorActionPreference = "SilentlyContinue"

# Working directory - use LocalAppData\Overlord\IrayServer
$overlordDir = Join-Path $env:LOCALAPPDATA "Overlord"
$irayServerDir = Join-Path $overlordDir "IrayServer"

# Step 1: Kill Iray Server processes
$processNames = @("iray_server", "iray_server_worker")

foreach ($processName in $processNames) {
    $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
    foreach ($process in $processes) {
        try {
            $process.Kill()
        } catch {
            # Ignore termination errors
        }
    }
}

# Wait a moment for processes to fully terminate
Start-Sleep -Seconds 2

# Step 2: Delete entire IrayServer folder if it exists
if (Test-Path $irayServerDir) {
    # Retry loop for folder deletion (in case files are still locked)
    $retryCount = 0
    $maxRetries = 10
    
    while ((Test-Path $irayServerDir) -and ($retryCount -lt $maxRetries)) {
        try {
            Remove-Item -Path $irayServerDir -Recurse -Force -ErrorAction Stop
            break
        } catch {
            Start-Sleep -Seconds 1
            $retryCount++
        }
    }
}