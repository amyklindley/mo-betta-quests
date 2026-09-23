@echo off
setlocal
set "DEST=%LOCALAPPDATA%\MoBettaQuests"
echo.
echo  Mo Betta Quests - quest overlay for Monsters ^& Memories
echo  Installing to %DEST%
echo.
if not exist "%~dp0MoBettaQuests.exe" (
    echo  MoBettaQuests.exe not found next to this script. Unzip everything first.
    pause
    exit /b 1
)
taskkill /im MoBettaQuests.exe /f >nul 2>&1
if not exist "%DEST%" mkdir "%DEST%"

rem Upgrade from the old "MnM Quests" install: keep its done/hidden marks, remove the rest.
set "OLD=%LOCALAPPDATA%\MnMQuests"
if exist "%OLD%" (
    taskkill /im MnMQuests.exe /f >nul 2>&1
    if exist "%OLD%\state.json" if not exist "%DEST%\state.json" copy /y "%OLD%\state.json" "%DEST%\" >nul
    if exist "%OLD%\overlay_pos.json" if not exist "%DEST%\overlay_pos.json" copy /y "%OLD%\overlay_pos.json" "%DEST%\" >nul
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MnMQuests /f >nul 2>&1
    del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\MnM Quests.lnk" 2>nul
    rmdir /s /q "%OLD%" 2>nul
    echo  Upgraded from MnM Quests; your done/hidden marks were kept.
)
copy /y "%~dp0MoBettaQuests.exe" "%DEST%\" >nul
copy /y "%~dp0README.md" "%DEST%\" >nul
copy /y "%~dp0uninstall.bat" "%DEST%\" >nul

rem Start Menu shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Programs')+'\Mo Betta Quests.lnk');" ^
  "$s.TargetPath='%DEST%\MoBettaQuests.exe'; $s.WorkingDirectory='%DEST%'; $s.Description='Quest overlay for Monsters & Memories'; $s.Save()"

echo  Installed. "Mo Betta Quests" is in your Start Menu.
echo.
choice /c YN /m "  Start Mo Betta Quests automatically with Windows"
if errorlevel 2 goto run
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MoBettaQuests /t REG_SZ /d "\"%DEST%\MoBettaQuests.exe\"" /f >nul
echo  Added to startup. (Turn it off later from the tray icon menu.)

:run
echo.
echo  Starting it now. Look for the gold check icon in your system tray.
echo  Hotkey: Ctrl+Shift+Q shows or hides the overlay.
start "" "%DEST%\MoBettaQuests.exe"
timeout /t 4 >nul
endlocal
