; Custom NSIS installer script for Overlord
; This script adds checkboxes for desktop shortcut and PATH environment variable

; Installer images
!undef MUI_WELCOMEFINISHPAGE_BITMAP
!define MUI_WELCOMEFINISHPAGE_BITMAP "${__FILEDIR__}\images\welcomeFinishImage.bmp"

!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "${__FILEDIR__}\images\headerInstallImage.bmp"
!define MUI_HEADERIMAGE_RIGHT

; Uninstaller images
!undef MUI_UNWELCOMEFINISHPAGE_BITMAP
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${__FILEDIR__}\images\welcomeFinishImage.bmp"
!define MUI_UNHEADERIMAGE
!define MUI_UNHEADERIMAGE_BITMAP "${__FILEDIR__}\images\headerInstallImage.bmp"
!define MUI_UNHEADERIMAGE_RIGHT

; Welcome page customization
!define MUI_WELCOMEPAGE_TITLE "Welcome to Overlord Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the uninstallation of Overlord.$\r$\n$\r$\nIt is recommended that you close all other applications. This will make it possible to update relevant system files without having to reboot your computer.$\r$\n$\r$\nClick Next to continue."

; License page customization
!define MUI_LICENSEPAGE_TEXT_TOP "Please review the license agreement before installing Overlord. Press Page Down to see the rest of the agreement."
!define MUI_LICENSEPAGE_TEXT_BOTTOM "If you accept the terms of the agreement, click I Agree to continue. You must accept the agreement to install Overlord."
!define MUI_LICENSEPAGE_BUTTON "I &Agree"

; Finish page customization
!define MUI_FINISHPAGE_TITLE "Overlord Installation Complete"
!define MUI_FINISHPAGE_TEXT "Overlord has been successfully installed on your computer.$\r$\n$\r$\nClick Finish to close this wizard."
!define MUI_FINISHPAGE_LINK "Visit Overlord on GitHub"
!define MUI_FINISHPAGE_LINK_LOCATION "https://github.com/Vineyard-Technologies/Overlord"

; Uninstaller page customization
!define MUI_UNWELCOMEPAGE_TITLE "Uninstall Overlord"
!define MUI_UNWELCOMEPAGE_TEXT "This wizard will guide you through the uninstallation of Overlord.$\r$\n$\r$\nBefore starting the uninstallation, make sure Overlord is not running.$\r$\n$\r$\nClick Next to continue."
!define MUI_UNFINISHPAGE_TITLE "Overlord Uninstallation Complete"
!define MUI_UNFINISHPAGE_TEXT "Overlord has been successfully removed from your computer.$\r$\n$\r$\nClick Finish to close this wizard."

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
