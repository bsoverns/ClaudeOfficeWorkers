@echo off
rem Builds dist\ClaudeOffice\ClaudeOffice.exe and dist\ClaudeOffice.zip (copy the zip to another PC).
rem Needs Python only on the PC that builds it. Run from anywhere: it works from the repo root.
cd /d "%~dp0.."
py -m pip install --upgrade pyinstaller || goto :fail
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
exit /b 0
:fail
echo Build failed.
exit /b 1
