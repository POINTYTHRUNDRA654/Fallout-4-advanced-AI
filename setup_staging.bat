@echo off
echo ========================================
echo Fallout 4 Advanced AI - Setup Staging
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
	echo ERROR: Python not found in PATH
	echo Please install Python 3.12+ and add to PATH
	pause
	exit /b 1
)

echo Running staging setup script...
echo.

python tools\setup_staging_directory.py

echo.
echo ========================================
echo Setup completed!
echo Check release_staging\core\ for structure
echo ========================================
echo.
pause
