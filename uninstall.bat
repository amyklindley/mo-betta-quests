@echo off
setlocal
set "DEST=%LOCALAPPDATA%\MoBettaQuests"
echo.
echo  Removing Mo Betta Quests from %DEST%
taskkill /im MoBettaQuests.exe /f >nul 2>&1
taskkill /im MnMQuests.exe /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MnMQuests /f >nul 2>&1
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\MnM Quests.lnk" 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MoBettaQuests /f >nul 2>&1
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Mo Betta Quests.lnk" 2>nul
choice /c YN /m "  Also delete your done/hidden marks (state.json)"
if errorlevel 2 (
    del /q "%DEST%\MoBettaQuests.exe" "%DEST%\README.md" "%DEST%\MoBettaQuests.log" "%DEST%\overlay_pos.json" "%DEST%\quests.md" 2>nul
    echo  Kept %DEST%\state.json
) else (
    cd /d "%TEMP%"
    rmdir /s /q "%DEST%" 2>nul
)
echo.
echo  Done. The quest block in the game's /note window is left as is; delete it in-game if you want.
pause
endlocal
