@echo off
rem Builds dist\MnMQuests.exe (overlay + note sync, no Python needed to run it).
cd /d "%~dp0"
python -m pip install --quiet pyinstaller
python -m PyInstaller --onefile --noconsole --name MnMQuests --clean overlay.py
if errorlevel 1 exit /b 1
copy /y README.md dist\README.md >nul
echo.
echo Built dist\MnMQuests.exe
