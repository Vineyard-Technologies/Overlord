$ErrorActionPreference = "SilentlyContinue"

# Working directory - use LocalAppData\Overlord\IrayServer
$overlordDir = Join-Path $env:LOCALAPPDATA "Overlord"
$irayServerDir = Join-Path $overlordDir "IrayServer"

echo "[INFO] ========== Step 1: Process Termination =========="
$processNames = @("iray_server", "iray_server_worker")
echo "[INFO] Target process names: $($processNames -join ', ')"

$totalProcessesKilled = 0
foreach ($processName in $processNames) {
    echo "[INFO] Searching for processes named: $processName"
    $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
    
    if ($processes) {
        echo "[INFO] Found $($processes.Count) process(es) named '$processName'"
        foreach ($process in $processes) {
            echo "[INFO] Attempting to kill process: $processName (PID: $($process.Id))"
            try {
                $process.Kill()
                echo "[SUCCESS] Successfully killed process: $processName (PID: $($process.Id))"
                $totalProcessesKilled++
            } catch {
                echo "[ERROR] Failed to kill process: $processName (PID: $($process.Id)). Error: $($_.Exception.Message)"
            }
        }
    } else {
        echo "[INFO] No processes found named: $processName"
    }
}

echo "[INFO] Total processes killed: $totalProcessesKilled"

echo "[INFO] ========== Step 2: Directory Cleanup =========="
if (Test-Path $irayServerDir) {
    echo "[INFO] IrayServer directory exists: $irayServerDir"
    
    # Get all items inside the IrayServer folder
    $items = Get-ChildItem -Path $irayServerDir -Force -ErrorAction SilentlyContinue
    
    if ($items) {
        echo "[INFO] Found $($items.Count) item(s) to delete in IrayServer directory"
        
        # Log what we're about to delete
        foreach ($item in $items) {
            if ($item.PSIsContainer) {
                echo "[INFO] Directory to delete: $($item.Name)"
            } else {
                echo "[INFO] File to delete: $($item.Name) ($($item.Length) bytes)"
            }
        }
        
        # Retry loop for content deletion (in case files are still locked)
        $retryCount = 0
        $maxRetries = 10
        do {
            $retryCount++
            echo "[INFO] Deletion attempt $retryCount of $maxRetries"
            
            $remainingItems = Get-ChildItem -Path $irayServerDir -Force -ErrorAction SilentlyContinue
            if (-not $remainingItems) {
                echo "[SUCCESS] All items successfully deleted from IrayServer directory"
                break
            }
            
            echo "[INFO] Attempting to delete $($remainingItems.Count) remaining item(s)"
            $deletedThisRound = 0
            foreach ($item in $remainingItems) {
                try {
                    echo "[INFO] Deleting: $($item.Name)"
                    Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
                    echo "[SUCCESS] Successfully deleted: $($item.Name)"
                    $deletedThisRound++
                } catch {
                    echo "[ERROR] Failed to delete: $($item.Name). Error: $($_.Exception.Message)"
                }
            }
            
            echo "[INFO] Deleted $deletedThisRound item(s) in this round"
            
            if ($retryCount -lt $maxRetries) {
                echo "[INFO] Waiting 1 second before next retry..."
                Start-Sleep -Seconds 1
            }
        } while ($remainingItems -and $retryCount -lt $maxRetries)
        
        # Final check
        $finalItems = Get-ChildItem -Path $irayServerDir -Force -ErrorAction SilentlyContinue
        if ($finalItems) {
            echo "[WARN] Warning: $($finalItems.Count) item(s) could not be deleted after $maxRetries attempts"
            foreach ($item in $finalItems) {
                echo "[WARN] Remaining item: $($item.Name)"
            }
        } else {
            echo "[SUCCESS] Directory cleanup completed successfully"
        }
    } else {
        echo "[INFO] IrayServer directory is already empty"
    }
} else {
    echo "[INFO] IrayServer directory does not exist: $irayServerDir"
}