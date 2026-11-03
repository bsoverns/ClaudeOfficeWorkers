@echo off
rem Builds dist\ClaudeOffice\ClaudeOffice.exe and dist\ClaudeOffice.zip, and dist\CursorOffice\CursorOffice.exe
rem and dist\CursorOffice.zip, and dist\UsageWidget\UsageWidget.exe and dist\UsageWidget.zip (copy a zip to another PC).
rem "build.bat cursor" builds only the Cursor office, "build.bat widget" only the widget. A build on main also copies
rem the widget to ..\@ActiveInProduction\UsageWidget if that folder's parent exists (scripts\copy_widget.ps1).
rem Needs Python only on the PC that builds it. Run from anywhere: it works from the repo root.
cd /d "%~dp0.."
py -m pip install --upgrade pyinstaller || goto :fail
if /i "%~1"=="cursor" goto :cursor
if /i "%~1"=="widget" goto :widget
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
if /i "%~1"=="cursor" exit /b 0
:widget
py tools\make_icon.py || goto :fail
py -m PyInstaller --noconfirm --clean --windowed --onefile --name UsageWidget --distpath dist\UsageWidget --icon office.ico src\usage_widget.py || goto :fail
copy /y "README.md" "dist\UsageWidget\" >nul
copy /y "LICENSE" "dist\UsageWidget\" >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\UsageWidget -DestinationPath dist\UsageWidget.zip" || goto :fail
echo.
echo Built dist\UsageWidget\UsageWidget.exe and dist\UsageWidget.zip
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\copy_widget.ps1 || goto :fail
exit /b 0
:fail
echo Build failed.
exit /b 1
