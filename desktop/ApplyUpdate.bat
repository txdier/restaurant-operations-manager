@echo off
setlocal EnableExtensions
set "PACKAGE=%~1"
if not defined PACKAGE (
  for /f "delims=" %%F in ('dir /b /o-d "%~dp0RestaurantManager-Update-*.zip" 2^>nul') do if not defined PACKAGE set "PACKAGE=%~dp0%%F"
)
if not defined PACKAGE (
  echo Please drag RestaurantManager-Update-x.y.z.zip onto this script.
  pause
  exit /b 1
)
"%~dp0RestaurantManagerUpdater.exe" "%PACKAGE%" --install-dir "%LOCALAPPDATA%\Programs\RestaurantManager"
if errorlevel 1 (
  echo Update failed. The previous program was preserved or restored.
  pause
  exit /b 1
)
echo Update completed.
