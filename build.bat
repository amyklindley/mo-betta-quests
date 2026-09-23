@echo off
rem Builds dist\MoBettaQuests.exe and dist\MoBettaQuests-win64.zip (exe + install scripts + README).
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt
python make_icon.py
python -m PyInstaller --onefile --noconsole --icon icon.ico --name MoBettaQuests --clean overlay.py
if errorlevel 1 exit /b 1
copy /y README.md dist\ >nul
copy /y install.bat dist\ >nul
copy /y uninstall.bat dist\ >nul
del /q dist\MoBettaQuests-win64.zip 2>nul
powershell -NoProfile -Command "Compress-Archive -Path dist\MoBettaQuests.exe, dist\install.bat, dist\uninstall.bat, dist\README.md -DestinationPath dist\MoBettaQuests-win64.zip"
echo.
echo Built dist\MoBettaQuests.exe and dist\MoBettaQuests-win64.zip
