@echo off
rem Builds dist\ClaudeOffice\ClaudeOffice.exe and dist\ClaudeOffice.zip (copy the zip to another PC).
rem Needs Python only on the PC that builds it.
cd /d "%~dp0"
py -m pip install --upgrade pyinstaller || goto :fail
py make_icon.py || goto :fail
py -m PyInstaller --noconfirm --clean --windowed --onedir --name ClaudeOffice --icon office.ico --add-data "index.html;." app.py || goto :fail
copy /y "README.md" "dist\ClaudeOffice\" >nul
copy /y "LICENSE" "dist\ClaudeOffice\" >nul
copy /y "CONNECT_A_PROJECT.md" "dist\ClaudeOffice\" >nul
copy /y "Connect Claude Code.bat" "dist\ClaudeOffice\" >nul
copy /y "Disconnect Claude Code.bat" "dist\ClaudeOffice\" >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\ClaudeOffice -DestinationPath dist\ClaudeOffice.zip" || goto :fail
echo.
echo Built dist\ClaudeOffice\ClaudeOffice.exe and dist\ClaudeOffice.zip
exit /b 0
:fail
echo Build failed.
exit /b 1
