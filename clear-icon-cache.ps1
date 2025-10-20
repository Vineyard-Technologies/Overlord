# Clear Windows Icon Cache
# This script clears the Windows icon cache to show updated executable icons

Write-Host "Clearing Windows Icon Cache..." -ForegroundColor Cyan

# Stop Explorer
Write-Host "Stopping Windows Explorer..." -ForegroundColor Yellow
Stop-Process -Name explorer -Force

# Wait a moment
Start-Sleep -Seconds 2

# Clear icon cache files
$iconcache = @(
    "$env:LOCALAPPDATA\IconCache.db",
    "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\iconcache_*.db"
)

foreach ($cache in $iconcache) {
    $files = Get-Item $cache -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Remove-Item $file.FullName -Force -ErrorAction Stop
            Write-Host "✓ Deleted: $($file.Name)" -ForegroundColor Green
        } catch {
            Write-Host "✗ Could not delete: $($file.Name) - $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# Also clear thumbnail cache (optional but recommended)
$thumbcache = Get-Item "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\thumbcache_*.db" -ErrorAction SilentlyContinue
foreach ($file in $thumbcache) {
    try {
        Remove-Item $file.FullName -Force -ErrorAction Stop
        Write-Host "✓ Deleted thumbnail cache: $($file.Name)" -ForegroundColor Green
    } catch {
        Write-Host "✗ Could not delete: $($file.Name)" -ForegroundColor Yellow
    }
}

# Restart Explorer
Write-Host "`nRestarting Windows Explorer..." -ForegroundColor Yellow
Start-Process explorer.exe

Write-Host "`n✓ Icon cache cleared successfully!" -ForegroundColor Green
Write-Host "The new icon should now appear in Windows Explorer." -ForegroundColor Cyan
Write-Host "`nNote: If icons still don't update, you may need to:" -ForegroundColor Yellow
Write-Host "  1. Log out and log back in" -ForegroundColor Yellow
Write-Host "  2. Or restart your computer" -ForegroundColor Yellow
