#!/bin/bash
# Removes the Claude Office hooks from Claude Code.
cd "$(dirname "$0")"
./ClaudeOffice.app/Contents/MacOS/ClaudeOffice --install --uninstall
echo; read -n 1 -s -r -p "Press any key to close."
