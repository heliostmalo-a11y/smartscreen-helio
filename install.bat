@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   SmartScreen Helio - installation
echo ============================================
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY ( where python >nul 2>nul && set PY=python )
if not defined PY (
  echo Python 3.10 ou plus recent est introuvable.
  echo Installe-le depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH", puis relance install.bat
  pause
  exit /b 1
)
echo [1/3] Creation de l'environnement Python (.venv)...
%PY% -m venv .venv || goto :err
echo [2/3] Installation des modules (PySide6, hidapi, Pillow, psutil)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
echo [3/3] Raccourci sur le Bureau...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\create_shortcut.ps1" -AppDir "%~dp0."
echo.
echo Installation terminee. Lance "SmartScreen Helio" depuis le Bureau.
echo (Pense a fermer le logiciel d'origine "3.5 Inch SmartMonitor" avant.)
pause
exit /b 0
:err
echo.
echo ERREUR pendant l'installation. Copie le message ci-dessus et envoie-le a Claude.
pause
exit /b 1
