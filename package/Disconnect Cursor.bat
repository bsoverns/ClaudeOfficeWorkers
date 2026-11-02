@echo off
rem Disconnects Cursor from the Cursor office.
cd /d "%~dp0"
CursorOffice.exe --install --uninstall
