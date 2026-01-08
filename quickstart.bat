@echo off
setlocal enabledelayedexpansion
title BackendBuddy - Project Manager

:menu
cls
echo.
echo ==============================================================================
echo.
echo   [ BACKEND BUDDY ]
echo   Projekt Manager v2.0
echo. 
echo ==============================================================================
echo.
echo   [1]  ROCKET START       (Launch App + API)
echo   [2]  NUKE EVERYTHING    (Kill all processes AND Clear ports)
echo   [3]  MANAGE VENV        (Reinstall/Fix Python Environment)
echo   [4]  INSTALL DEPS       (Install Dependencies Manual)
echo   [5]  EXIT
echo   [6]  SECURE START       (HTTPS Mode)
echo.
echo ==============================================================================
echo.

set /p opt="Select an option (1-5): "

if "%opt%"=="6" goto start_https
if "%opt%"=="5" goto exit
if "%opt%"=="4" goto install_deps
if "%opt%"=="3" goto manage_venv
if "%opt%"=="2" goto nuke
if "%opt%"=="1" goto start

echo.
echo [ERROR] Invalid option selected.
pause
goto menu

:start
cls
echo.
echo [CHECKING PORTS]
echo.

REM --- Check Frontend Port 1337 ---
netstat -ano | findstr :1337 | findstr LISTEN >nul
if errorlevel 1 goto check_backend

echo [WARNING] Port 1337 (Frontend) is busy.
echo.
set /p nukesel="Nuke it and continue? (Y/N): "
if /I "%nukesel%"=="N" goto menu
echo Killing Node...
taskkill /F /IM node.exe /T 2>nul


:check_backend
REM --- Check Backend Port 1338 ---
netstat -ano | findstr :1338 | findstr LISTEN >nul
if errorlevel 1 goto launch_servers

echo [WARNING] Port 1338 (Backend) is busy.
echo.
set /p nukesel="Nuke it and continue? (Y/N): "
if /I "%nukesel%"=="N" goto menu
echo Killing Python...
taskkill /F /IM python.exe /T 2>nul


:launch_servers
echo.
echo [STARTING SERVERS]
echo.

cd backend
if exist "venv" goto run_backend

echo [INFO] Venv missing! Creating...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt

:run_backend
cd ..

REM Start Backend
echo Starting API on 1338...
start "BackendBuddy API (1338)" cmd /k "cd backend && venv\Scripts\activate.bat && python main.py"

REM Wait for backend
timeout /t 2 /nobreak >nul

REM Start Frontend
echo Starting App on 1337...
start "BackendBuddy App (1337)" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo        BACKEND BUDDY IS LIVE
echo ========================================
echo.
echo   App UI:    http://localhost:1337
echo   API:       http://localhost:1338
echo.
echo   Closing this window will NOT stop servers.
echo   Use option [2] NUKE to stop them.
echo.
pause
start http://localhost:1337
goto exit


:start_https
cls
echo.
echo [STARTING IN SECURE MODE (HTTPS)]
echo.

REM Set env vars for HTTPS
set HTTPS=true
set USE_HTTPS=true

cd backend
if exist "venv" goto run_backend_https

echo [INFO] Venv missing! Creating...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt

:run_backend_https
cd ..

REM Start Backend
echo Starting API on 1338 (HTTPS)...
start "BackendBuddy API (Secure)" cmd /k "cd backend && venv\Scripts\activate.bat && python main.py"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM Start Frontend
echo Starting App on 1337 (HTTPS)...
start "BackendBuddy App (Secure)" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo        SECURE MODE IS LIVE
echo ========================================
echo.
echo   App UI:    https://localhost:1337
echo   API:       https://localhost:1338
echo.
echo   Note: Acccept the self-signed cert warning in browser.
echo.
pause
start https://localhost:1337
goto exit


:nuke
cls
echo.
echo [NUKING PROCESSES]
echo.
echo Killing Python...
taskkill /F /IM python.exe /T 2>nul
echo Killing Node...
taskkill /F /IM node.exe /T 2>nul
echo Killing Cloudflared...
taskkill /F /IM cloudflared.exe /T 2>nul
echo.
echo [CLEANUP COMPLETE]
pause
goto menu


:manage_venv
cls
echo.
echo [MANAGE VIRTUAL ENVIRONMENT]
echo.
echo   [1] REINSTALL (Delete & Recreate)
echo   [2] BACK
echo.
set /p venvopt="Select option: "

if "%venvopt%"=="2" goto menu
if not "%venvopt%"=="1" goto manage_venv

echo.
echo Deleting venv...
rmdir /s /q backend\venv
echo Creating new venv...
cd backend
python -m venv venv
echo Installing dependencies...
venv\Scripts\activate.bat && pip install -r requirements.txt
cd ..
echo.
echo [DONE]
pause
goto menu


:install_deps
cls
echo.
echo [INSTALLING DEPENDENCIES]
echo.
echo Backend...
cd backend
venv\Scripts\activate.bat && pip install -r requirements.txt
cd ..
echo Frontend...
cd frontend
npm install
cd ..
echo.
echo [DONE]
pause
goto menu


:exit
exit /b
