#!/bin/bash
# Connects every Claude Code session on this Mac to the Claude Office (run once, and again if you move this folder).
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine . 2>/dev/null
./ClaudeOffice.app/Contents/MacOS/ClaudeOffice --install
echo; read -n 1 -s -r -p "Done. Restart any open Claude Code sessions. Press any key to close."
