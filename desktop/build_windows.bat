@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

where py >nul 2>nul || (echo [ERROR] Python launcher not found.& exit /b 1)
where npm >nul 2>nul || (echo [ERROR] npm not found.& exit /b 1)

for /f "delims=" %%V in ('py -3.8 -c "import sys; print(sys.version_info[:2])" 2^>nul') do set PYOK=%%V
if not defined PYOK (echo [ERROR] Install 64-bit Python 3.8.10.& exit /b 1)

if not exist .venv-win7 py -3.8 -m venv .venv-win7
call .venv-win7\Scripts\activate.bat
set "PYTHONPATH=%CD%\desktop"
python -m pip install --upgrade pip==24.0
if errorlevel 1 exit /b 1
python -m pip install -r desktop\requirements-win7.txt
if errorlevel 1 exit /b 1

call npm ci
if errorlevel 1 exit /b 1
call npm run desktop:build
if errorlevel 1 exit /b 1
node desktop\check_web_compat.mjs
if errorlevel 1 exit /b 1

python -m pytest desktop\tests
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm desktop\restaurant-manager.spec
if errorlevel 1 exit /b 1
python -m PyInstaller --clean --noconfirm desktop\updater.spec
if errorlevel 1 exit /b 1

copy /y desktop\app-manifest.json dist\RestaurantManager\app-manifest.json >nul

set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (echo [ERROR] Install Inno Setup 6.& exit /b 1)
"%ISCC%" desktop\installer.iss
if errorlevel 1 exit /b 1

echo Build completed: release\RestaurantManager-Setup-1.0.6.exe
