r"""ClaudeOffice.exe: the whole Claude Office in one program (built by scripts/build.bat).

  ClaudeOffice.exe                     open the office in its own window (starts the server;
                                       it shuts down shortly after the window is closed)
  ClaudeOffice.exe --server [port]     run the server only, no window, until stopped
  ClaudeOffice.exe --install [--project C:\repo] [--uninstall]
                                       connect Claude Code (same as src/install_hooks.py)
  ClaudeOffice.exe --hook              what Claude Code runs for each event (reads stdin)
  ClaudeOffice.exe cmd <args>          same as src/office.py, e.g. cmd start "Test" / cmd demo

The Cursor office is its own program, CursorOffice.exe: see cursor_app.py, which runs this file's
main() with cursor=True. That turns its arguments into the --cursor ones below (cursor_args).

Also runs unbuilt: `py src/app.py ...`.

On a Mac, ClaudeOffice.app (built by scripts/build_mac.sh) runs this file with the Mac's own
python3 and takes the same arguments: ClaudeOffice.app/Contents/MacOS/ClaudeOffice --install, etc.
"""
from __future__ import annotations

import os
import sys
import time

FROZEN = getattr(sys, "frozen", False)
BYE_EXIT_SECONDS = 15      # app mode: quit this long after a window said goodbye, if no page polled since
                           # (a reload or a second window keeps it alive; silence alone never quits it,
                           # since minimized windows, sleeping tabs and PC sleep pause the polling too)
NO_WINDOW_EXIT_SECONDS = 120   # app mode: quit if no page has polled at all this long after start
                               # (the browser failed to open the window)


def attach_console() -> bool:
    """The exe has no console of its own; borrow the one it was started from, if any."""
    if not FROZEN or os.name != "nt":
        return True
    import ctypes
    import msvcrt
    get = ctypes.windll.kernel32.GetStdHandle
    get.restype = ctypes.c_void_p
    handle = get(-11)  # STD_OUTPUT_HANDLE: set when output is redirected to a file or pipe
    if handle and handle != ctypes.c_void_p(-1).value:
        try:
            sys.stdout = open(msvcrt.open_osfhandle(handle, os.O_WRONLY), "w", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
            return True
        except OSError:
            pass
    if ctypes.windll.kernel32.AttachConsole(-1):
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = sys.stdout
        return True
    return False


def tell(text: str, title: str = "", error: bool = False) -> None:
    """Print if there's a console, otherwise show a message box (double-clicked .bat/.exe)."""
    if not FROZEN or _has_console:
        print(text)
        return
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title or _app_name, 0x10 if error else 0x40)


_has_console = False
_app_name = "Claude Office"


def cursor_args(args: list[str]) -> list[str]:
    """CursorOffice.exe's arguments as the ones main() knows, so it's always the Cursor office."""
    if not args:
        return ["--cursor"]
    if args[0] == "--server":
        return ["--server", "--cursor", *args[1:]]
    if args[0] in ("--hook", "--install", "--cost-check"):
        return ["--cursor-" + args[0][2:], *args[1:]]
    return args


def find_browser() -> str | None:
    """Edge (on every Windows 11 PC) or Chrome: both can open a page as its own app window.
    On a Mac: Chrome, Edge, Brave, Chromium or Vivaldi from /Applications or ~/Applications."""
    if sys.platform == "darwin":
        names = [("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge"),
                 ("Brave Browser", "Brave Browser"), ("Chromium", "Chromium"), ("Vivaldi", "Vivaldi")]
        roots = ["/Applications", os.path.expanduser("~/Applications")]
        mac = [os.path.join(r, f"{app}.app", "Contents", "MacOS", exe) for r in roots for app, exe in names]
        return next((c for c in mac if os.path.isfile(c)), None)
    env = os.environ
    candidates = [
        os.path.join(env.get("ProgramFiles(x86)", ""), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(env.get("ProgramFiles", ""), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(env.get("ProgramFiles", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(env.get("ProgramFiles(x86)", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(env.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def open_window(url: str) -> None:
    import subprocess   # these imports are here, not at the top, so the hook modes start fast
    import webbrowser
    from server import data_dir
    browser = find_browser()
    if not browser:
        webbrowser.open(url)
        return
    # Its own profile keeps the window separate from your normal browser and remembers
    # the office's settings (sound, notification permission).
    profile = os.path.join(data_dir(), "window")
    os.makedirs(profile, exist_ok=True)
    subprocess.Popen([browser, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1500,900",
                      "--no-first-run", "--no-default-browser-check"],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     start_new_session=(os.name != "nt"),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_app() -> None:
    import threading
    import server
    port = server.default_port()
    url = f"http://127.0.0.1:{port}/"
    try:
        httpd = server.make_server(port)
    except OSError:
        open_window(url)        # already running (another window or --server): just show it
        return
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    open_window(url)
    started = time.time()
    while True:
        time.sleep(5)
        never_loaded = not server.VIEWERS.ever_seen() and time.time() - started > NO_WINDOW_EXIT_SECONDS
        if never_loaded or server.VIEWERS.gone_for() > BYE_EXIT_SECONDS:
            httpd.shutdown()
            return


def main(cursor: bool = False) -> None:
    global _has_console, _app_name
    args = sys.argv[1:]
    if cursor:
        _app_name = "Cursor Office"
        args = cursor_args(args)
        if args[:1] == ["cmd"]:     # office.py talks to this office, not the Claude one
            os.environ["CLAUDE_OFFICE_PORT"] = os.environ.get("CURSOR_OFFICE_PORT") or "8778"
    if args[:1] == ["--hook"]:
        import claude_hook
        try:
            claude_hook.main()
        except Exception:
            pass
        sys.exit(0)
    if args[:1] == ["--cursor-hook"]:
        attach_console()    # for the reply, where stdout is a pipe (PowerShell doesn't read a windowed exe's)
        import cursor_hook
        try:
            cursor_hook.main()
        except Exception:
            pass
        sys.exit(0)
    if args[:1] == ["--cursor-cost-check"]:
        _has_console = attach_console()
        import server
        tell(server.cursor_cost_report(), "Cursor cost check")
        return
    if args[:1] in (["--install"], ["--cursor-install"]):
        _has_console = attach_console()
        is_cursor = args[0] == "--cursor-install"
        if is_cursor:
            import install_cursor_hooks as installer
        else:
            import install_hooks as installer
        rest = args[1:]
        project = None
        if "--project" in rest:
            i = rest.index("--project")
            project = rest[i + 1] if i + 1 < len(rest) else "."
        try:
            tell(installer.install(project, "--uninstall" in rest))
        except Exception as e:
            tell(f"Couldn't update the {'Cursor hooks' if is_cursor else 'Claude Code settings'}:\n{e}", error=True)
            sys.exit(1)
        return
    if args[:1] == ["--cursor"]:
        import server
        server.use_cursor()
        run_app()
        return
    if args[:1] == ["--server"]:
        _has_console = attach_console()
        import server
        server.main(args[1:])
        return
    if args[:1] == ["cmd"]:
        _has_console = attach_console()
        import office
        office.main(args[1:])
        return
    if args and args[0] in ("-h", "--help", "/?"):
        _has_console = attach_console()
        if cursor:
            import cursor_app
            tell(cursor_app.__doc__ or "")
        else:
            tell(__doc__ or "")
        return
    run_app()


if __name__ == "__main__":
    main()
