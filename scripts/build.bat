@echo off
rem Builds dist\ClaudeOffice\ClaudeOffice.exe and dist\ClaudeOffice.zip, and dist\CursorOffice\CursorOffice.exe
rem and dist\CursorOffice.zip (copy a zip to another PC). "build.bat cursor" builds only the Cursor one.
rem Needs Python only on the PC that builds it. Run from anywhere: it works from the repo root.
cd /d "%~dp0.."
py -m pip install --upgrade pyinstaller || goto :fail
if /i "%~1"=="cursor" goto :cursor
py tools\make_icon.py || goto :fail
py -m PyInstaller --noconfirm --clean --windowed --onedir --name ClaudeOffice --icon office.ico --add-data "src\index.html;." src\app.py || goto :fail
copy /y "README.md" "dist\ClaudeOffice\" >nul
copy /y "LICENSE" "dist\ClaudeOffice\" >nul
copy /y "docs\CONNECT_A_PROJECT.md" "dist\ClaudeOffice\" >nul
copy /y "package\Connect Claude Code.bat" "dist\ClaudeOffice\" >nul
copy /y "package\Disconnect Claude Code.bat" "dist\ClaudeOffice\" >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\ClaudeOffice -DestinationPath dist\ClaudeOffice.zip" || goto :fail
echo.
echo Built dist\ClaudeOffice\ClaudeOffice.exe and dist\ClaudeOffice.zip
:cursor
py tools\make_icon.py --cursor || goto :fail
py -m PyInstaller --noconfirm --clean --windowed --onedir --name CursorOffice --icon cursor_office.ico --add-data "src\index.html;." src\cursor_app.py || goto :fail
copy /y "README.md" "dist\CursorOffice\" >nul
copy /y "LICENSE" "dist\CursorOffice\" >nul
copy /y "docs\CONNECT_A_PROJECT.md" "dist\CursorOffice\" >nul
copy /y "package\Connect Cursor.bat" "dist\CursorOffice\" >nul
copy /y "package\Disconnect Cursor.bat" "dist\CursorOffice\" >nul
copy /y "package\Check Cursor Cost.bat" "dist\CursorOffice\" >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\CursorOffice -DestinationPath dist\CursorOffice.zip" || goto :fail
echo.
echo Built dist\CursorOffice\CursorOffice.exe and dist\CursorOffice.zip
exit /b 0
:fail
echo Build failed.
exit /b 1
