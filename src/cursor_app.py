r"""CursorOffice.exe: the Cursor office as its own program (built by scripts/build.bat from app.py's code).

  CursorOffice.exe                     open the Cursor office in its own window (port 8778)
  CursorOffice.exe --server [port]     run its server only, no window, until stopped
  CursorOffice.exe --install [--project C:\repo] [--uninstall]
                                       connect Cursor (same as src/install_cursor_hooks.py)
  CursorOffice.exe --hook              what Cursor runs for each event (reads stdin)
  CursorOffice.exe --cost-check        what the cost screen finds here (no secrets in it)
  CursorOffice.exe cmd <args>          same as src/office.py, against this office

Also runs unbuilt: `py src/cursor_app.py ...`. On a Mac, CursorOffice.app does the same.
"""
from __future__ import annotations

import app

if __name__ == "__main__":
    app.main(cursor=True)
