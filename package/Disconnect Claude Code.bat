@echo off
rem Disconnects Claude Code from the Claude Office.
cd /d "%~dp0"
ClaudeOffice.exe --install --uninstall
