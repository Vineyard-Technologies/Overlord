; Custom NSIS installer script for Overlord
; This script adds checkboxes for desktop shortcut and PATH environment variable

!macro customHeader
  !system "echo Overlord Custom NSIS Script"
!macroend

!macro preInstall
  ; This runs before installation
!macroend

!macro customInstall
  ; Ask user about desktop shortcut
  MessageBox MB_YESNO "Create a desktop shortcut for Overlord?" IDYES createShortcut IDNO skipShortcut
  createShortcut:
    CreateShortcut "$DESKTOP\Overlord.lnk" "$INSTDIR\Overlord.exe"
  skipShortcut:
  
  ; Ask user about adding to PATH
  MessageBox MB_YESNO "Add Overlord to the system PATH?$\n$\nThis allows you to run Overlord from the command line." IDYES addPath IDNO skipPath
  addPath:
    ; Read current PATH
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    
    ; Check if already in PATH
    ${StrContains} $1 "$INSTDIR" "$0"
    StrCmp $1 "" 0 +3
      ; Not in PATH, add it
      WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" "$0;$INSTDIR"
      DetailPrint "Added Overlord to system PATH"
    
    ; Broadcast environment change
    SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
  skipPath:
!macroend

!macro customUnInstall
  ; Remove desktop shortcut if exists
  Delete "$DESKTOP\Overlord.lnk"
  
  ; Remove from PATH using PowerShell (escape $ with $$)
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$$path = [Environment]::GetEnvironmentVariable(\"Path\", \"Machine\"); $$newPath = ($$path -split \";\") | Where-Object { $$_ -ne \"$INSTDIR\" } | Select-Object -Unique; [Environment]::SetEnvironmentVariable(\"Path\", ($$newPath -join \";\"), \"Machine\")"'
  
  DetailPrint "Removed Overlord from system PATH"
  
  ; Broadcast environment change
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
!macroend
