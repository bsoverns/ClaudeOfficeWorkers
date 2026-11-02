@echo off
rem Opens the Cursor office: starts its own server process (port 8778) and the page.
cd /d "%~dp0..\src"
start "" http://127.0.0.1:8778/
py server.py --cursor %*
