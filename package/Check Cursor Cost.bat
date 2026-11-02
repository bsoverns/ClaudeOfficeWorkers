@echo off
rem Writes what the Cursor cost screen can find to cursor-cost-check.txt and opens it. It holds your own amounts and field names only, no login or team spend.
cd /d "%~dp0"
CursorOffice.exe --cost-check > cursor-cost-check.txt
start "" notepad cursor-cost-check.txt
