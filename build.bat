@echo off
echo Starting Elden Ring Launcher Build Process...

:: Check if ER_Launcher.exe is running
tasklist /FI "IMAGENAME eq ER_Launcher.exe" 2>NUL | find /I /N "ER_Launcher.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Error: 'ER_Launcher.exe' is currently running.
    echo Please close the launcher before building.
    pause
    exit /b 1
)

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b %errorlevel%
)

echo Installing/Updating dependencies...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b %errorlevel%
)

echo Building executable...
python build_exe.py

if %errorlevel% neq 0 (
    echo Error: Build failed.
    pause
    exit /b %errorlevel%
)

echo.
echo Build Successful! 
echo The executable is located in the 'dist' folder.
pause
