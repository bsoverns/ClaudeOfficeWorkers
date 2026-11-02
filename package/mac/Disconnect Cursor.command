#!/bin/bash
# Removes the office hooks from Cursor.
cd "$(dirname "$0")"
./CursorOffice.app/Contents/MacOS/CursorOffice --install --uninstall
echo; read -n 1 -s -r -p "Press any key to close."
