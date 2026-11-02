#!/bin/bash
# Connects every Cursor project on this Mac to the Cursor office (run once, and again if you move this folder).
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine . 2>/dev/null
./CursorOffice.app/Contents/MacOS/CursorOffice --install
echo; read -n 1 -s -r -p "Done. Press any key to close."
