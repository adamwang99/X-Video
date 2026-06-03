@echo off
REM X-Video Studio — Windows .exe Packager
REM Usage: scripts\package-windows.bat
echo 📦 Packaging X-Video Studio for Windows...

set APP_NAME=X-Video Studio
set VERSION=1.2.0
set DIST=dist\%APP_NAME%

rmdir /s /q "%DIST%" 2>nul
mkdir "%DIST%"

REM Copy files
xcopy /E /I backend "%DIST%\backend"
xcopy /E /I frontend "%DIST%\frontend"
xcopy /E /I output "%DIST%\output"
copy requirements.txt "%DIST%\"

REM Create launcher
(
echo @echo off
echo title X-Video Studio v%VERSION%
echo echo Starting X-Video Studio...
echo cd /d "%%~dp0"
echo pip install -q fastapi uvicorn 2^>nul
echo echo Opening browser...
echo start http://localhost:8767
echo python backend\server.py
echo pause
) > "%DIST%\xvideo.bat"

REM Create shortcut script
(
echo @echo off
echo start "" "%CD%\%DIST%\xvideo.bat"
) > "dist\X-Video Studio.lnk"

echo.
echo ✅ Done! Output: %DIST%
echo.
echo 📎 To install:
echo   1. Extract dist\X-Video Studio\ to C:\Program Files\
echo   2. Run C:\Program Files\X-Video Studio\xvideo.bat
echo   3. Browser opens at http://localhost:8767
