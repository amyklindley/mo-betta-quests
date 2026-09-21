@echo off
setlocal
set "DEST=%LOCALAPPDATA%\MnMQuests"
echo.
echo  MnM Quests - quest overlay for Monsters ^& Memories
echo  Installing to %DEST%
echo.
if not exist "%~dp0MnMQuests.exe" (
    echo  MnMQuests.exe not found next to this script. Unzip everything first.
    pause
    exit /b 1
)
taskkill /im MnMQuests.exe /f >nul 2>&1
if not exist "%DEST%" mkdir "%DEST%"
copy /y "%~dp0MnMQuests.exe" "%DEST%\" >nul
copy /y "%~dp0README.md" "%DEST%\" >nul
copy /y "%~dp0uninstall.bat" "%DEST%\" >nul

rem Start Menu shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Programs')+'\MnM Quests.lnk');" ^
  "$s.TargetPath='%DEST%\MnMQuests.exe'; $s.WorkingDirectory='%DEST%'; $s.Description='Quest overlay for Monsters & Memories'; $s.Save()"

echo  Installed. "MnM Quests" is in your Start Menu.
echo.
choice /c YN /m "  Start MnM Quests automatically with Windows"
if errorlevel 2 goto run
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MnMQuests /t REG_SZ /d "\"%DEST%\MnMQuests.exe\"" /f >nul
echo  Added to startup. (Turn it off later from the tray icon menu.)

:run
echo.
echo  Starting it now. Look for the gold check icon in your system tray.
echo  Hotkey: Ctrl+Shift+Q shows or hides the overlay.
start "" "%DEST%\MnMQuests.exe"
timeout /t 4 >nul
endlocal
