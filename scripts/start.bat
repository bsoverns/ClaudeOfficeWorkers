@echo off
rem Opens the Claude Office: starts the server and the page.
cd /d "%~dp0..\src"
start "" http://127.0.0.1:8777/
py server.py %*
