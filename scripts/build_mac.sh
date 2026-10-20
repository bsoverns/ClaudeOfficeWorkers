#!/bin/bash
# Builds dist/ClaudeOffice-mac/ClaudeOffice.app and dist/ClaudeOffice-mac.zip (copy the zip to another Mac).
# No PyInstaller: the app is a small launcher that runs src/ with the Mac's own python3, so the
# build runs on any machine with python3 and zip (CI builds it on macOS). Run from anywhere.
# VERSION=2026.10.20.1 scripts/build_mac.sh stamps that version into the app and VERSION.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=dist/ClaudeOffice-mac
APP="$OUT/ClaudeOffice.app/Contents"
VERSION="${VERSION:-dev}"
rm -rf "$OUT" dist/ClaudeOffice-mac.zip
mkdir -p "$APP/MacOS" "$APP/Resources/ClaudeOffice"
python3 tools/make_icon.py --icns
cp office.icns "$APP/Resources/office.icns"
cp src/*.py src/index.html "$APP/Resources/ClaudeOffice/"
cp package/mac/ClaudeOffice "$APP/MacOS/ClaudeOffice"
sed "s|<string>1.0</string>|<string>$VERSION</string>|g" package/mac/Info.plist > "$APP/Info.plist"
cp "package/mac/Connect Claude Code.command" "package/mac/Disconnect Claude Code.command" "$OUT/"
cp README.md LICENSE docs/CONNECT_A_PROJECT.md "$OUT/"
echo "$VERSION" > "$OUT/VERSION.txt"
chmod +x "$APP/MacOS/ClaudeOffice" "$OUT/"*.command
(cd dist && zip -qry ClaudeOffice-mac.zip ClaudeOffice-mac)
echo
echo "Built $OUT/ClaudeOffice.app and dist/ClaudeOffice-mac.zip"
