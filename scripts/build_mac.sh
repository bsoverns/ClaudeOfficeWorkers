#!/bin/bash
# Builds dist/ClaudeOffice-mac/ClaudeOffice.app and dist/ClaudeOffice-mac.zip, and the same for CursorOffice
# (copy a zip to another Mac).
# No PyInstaller: each app is a small launcher that runs src/ with the Mac's own python3, so the
# build runs on any machine with python3 and zip (CI builds it on macOS). Run from anywhere.
# VERSION=2026.10.20.1 scripts/build_mac.sh stamps that version into the apps and VERSION.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${VERSION:-dev}"

OUT=dist/ClaudeOffice-mac
APP="$OUT/ClaudeOffice.app/Contents"
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

OUT=dist/CursorOffice-mac
APP="$OUT/CursorOffice.app/Contents"
rm -rf "$OUT" dist/CursorOffice-mac.zip
mkdir -p "$APP/MacOS" "$APP/Resources/CursorOffice"
python3 tools/make_icon.py --cursor --icns
cp cursor_office.icns "$APP/Resources/office.icns"
cp src/*.py src/index.html "$APP/Resources/CursorOffice/"
cp package/mac/CursorOffice "$APP/MacOS/CursorOffice"
sed -e "s|<string>1.0</string>|<string>$VERSION</string>|g" -e "s|Claude Office|Cursor Office|g" \
    -e "s|claudeoffice|cursoroffice|g" -e "s|ClaudeOffice|CursorOffice|g" package/mac/Info.plist > "$APP/Info.plist"
cp "package/mac/Connect Cursor.command" "package/mac/Disconnect Cursor.command" "$OUT/"
cp README.md LICENSE docs/CONNECT_A_PROJECT.md "$OUT/"
echo "$VERSION" > "$OUT/VERSION.txt"
chmod +x "$APP/MacOS/CursorOffice" "$OUT/"*.command
(cd dist && zip -qry CursorOffice-mac.zip CursorOffice-mac)

echo
echo "Built dist/ClaudeOffice-mac/ClaudeOffice.app, dist/CursorOffice-mac/CursorOffice.app and their zips"
