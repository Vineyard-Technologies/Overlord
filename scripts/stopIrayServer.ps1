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

# Step 2: Delete contents of IrayServer folder if it exists (keep the folder itself)
if (Test-Path $irayServerDir) {
    # Get all items inside the IrayServer folder
    $items = Get-ChildItem -Path $irayServerDir -Force -ErrorAction SilentlyContinue
    
    if ($items) {
        # Retry loop for content deletion (in case files are still locked)
        do {
            $remainingItems = Get-ChildItem -Path $irayServerDir -Force -ErrorAction SilentlyContinue
            if (-not $remainingItems) {
                break
            }
            
            foreach ($item in $remainingItems) {
                try {
                    Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
                } catch {
                    # Continue trying other items even if one fails
                }
            }
            
            Start-Sleep -Seconds 1
        } while ($remainingItems)
    }
}