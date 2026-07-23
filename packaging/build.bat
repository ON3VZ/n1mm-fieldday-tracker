@echo off
REM ============================================================
REM  N1MM Field Day Tracker - one-click Windows build
REM  Dubbelklik dit bestand. Het bouwt de installer (setup.exe).
REM  Vereist: Python 3.11+ geinstalleerd (met "Add to PATH").
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo.
echo === N1MM Field Day Tracker - build ===
echo.

REM --- 1. Python controleren ---
python --version >nul 2>&1
if errorlevel 1 (
  echo [FOUT] Python niet gevonden. Installeer Python 3.11+ van python.org
  echo        en vink "Add python.exe to PATH" aan. Start dit script daarna opnieuw.
  pause
  exit /b 1
)

REM --- 2. Bouw-omgeving (aparte venv, raakt je gewone .venv niet) ---
if not exist ".venv-build" (
  echo [1/5] Bouw-omgeving aanmaken...
  python -m venv .venv-build
)
call .venv-build\Scripts\activate

echo [2/5] Benodigdheden installeren (PyInstaller + app-pakketten)...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt >nul
python -m pip install pyinstaller pywin32-ctypes >nul

REM --- 3. Versie uitlezen uit app\version.py ---
for /f "tokens=2 delims== " %%v in ('findstr /b "APP_VERSION" app\version.py') do (
  set APPVER=%%~v
)
set APPVER=%APPVER:"=%
echo [3/5] Versie: %APPVER%

REM --- 4. PyInstaller: bouw de .exe ---
echo [4/5] Applicatie bouwen met PyInstaller...
pyinstaller --noconfirm --clean packaging\tracker.spec
if errorlevel 1 (
  echo [FOUT] PyInstaller-build mislukt. Zie de meldingen hierboven.
  pause
  exit /b 1
)

REM --- 5. Inno Setup: bouw de installer ---
echo [5/5] Installer bouwen met Inno Setup...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
  echo.
  echo [LET OP] Inno Setup 6 is niet gevonden.
  echo Download en installeer het van https://jrsoftware.org/isdl.php
  echo Start daarna dit script opnieuw - de .exe staat al klaar in dist\.
  pause
  exit /b 1
)

"%ISCC%" /DAppVersion=%APPVER% packaging\installer.iss
if errorlevel 1 (
  echo [FOUT] Inno Setup-build mislukt.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  KLAAR! De installer staat in de map:  packaging\Output\
echo  Bestand: N1MMFieldDayTracker-Setup-%APPVER%.exe
echo.
echo  Deel dit bestand met je clubleden. Dubbelklikken en
echo  installeren - geen Python of commando's nodig.
echo ============================================================
echo.
pause
