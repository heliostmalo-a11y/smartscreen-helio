@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo ================================================
echo   Fabrication de l'installateur SmartScreen Helio
echo ================================================
if not exist ".venv\Scripts\python.exe" ( echo Lance d'abord install.bat & pause & exit /b 1 )

set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%P
if not defined ISCC ( echo Inno Setup 6 introuvable : https://jrsoftware.org/isdl.php & pause & exit /b 1 )

echo [1/4] PyInstaller...
".venv\Scripts\python.exe" -m pip install --quiet pyinstaller || goto :err
if exist build rmdir /s /q build
if exist "dist\SmartScreen Helio" rmdir /s /q "dist\SmartScreen Helio"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name "SmartScreen Helio" ^
  --icon "res\icons\app.ico" --hidden-import win32pdh --hidden-import hid --hidden-import serial.tools.list_ports --hidden-import usb.core --hidden-import usb.backend.libusb1 --hidden-import usb.backend.libusb0 --collect-submodules core.drivers ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf ^
  app.py || goto :err

echo [2/4] Copie des themes et ressources...
set OUT=dist\SmartScreen Helio
robocopy res "%OUT%\res" /E /NFL /NDL /NJH /NJS >nul
robocopy themes "%OUT%\themes" /E /XD _old _fichiers_mal_ranges /NFL /NDL /NJH /NJS >nul
copy /y LICENSE.txt "%OUT%\" >nul
if exist ssd.txt copy /y ssd.txt "%OUT%\" >nul

echo [3/4] Test rapide...
if not exist "%OUT%\SmartScreen Helio.exe" goto :err

echo [4/4] Installateur Inno Setup...
%ISCC% /Q "packaging\installer.iss" || goto :err
echo.
echo OK : l'installateur est dans le dossier "Installateur" (Bureau\SmartScreen_Helio\Installateur)
pause
exit /b 0
:err
echo.
echo ERREUR - copie le message ci-dessus et envoie-le a Claude.
pause
exit /b 1
