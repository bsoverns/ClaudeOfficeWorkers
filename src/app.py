r"""ClaudeOffice.exe: the whole Claude Office in one program (built by scripts/build.bat).

  ClaudeOffice.exe                     open the office in its own window (starts the server;
                                       it shuts down a minute after the window is closed)
  ClaudeOffice.exe --server [port]     run the server only, no window, until stopped
  ClaudeOffice.exe --install [--project C:\repo] [--uninstall]
                                       connect Claude Code (same as src/install_hooks.py)
  ClaudeOffice.exe --hook              what Claude Code runs for each event (reads stdin)
  ClaudeOffice.exe cmd <args>          same as src/office.py, e.g. cmd start "Test" / cmd demo

Also runs unbuilt: `py src/app.py ...`.

On a Mac, ClaudeOffice.app (built by scripts/build_mac.sh) runs this file with the Mac's own
python3 and takes the same arguments: ClaudeOffice.app/Contents/MacOS/ClaudeOffice --install, etc.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser

FROZEN = getattr(sys, "frozen", False)
IDLE_EXIT_SECONDS = 60     # app mode: quit when no window has been open this long


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


def tell(text: str, title: str = "Claude Office", error: bool = False) -> None:
    """Print if there's a console, otherwise show a message box (double-clicked .bat/.exe)."""
    if not FROZEN or _has_console:
        print(text)
        return
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 if error else 0x40)


_has_console = False


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


def data_dir() -> str:
    """Where the office keeps its own files: %LOCALAPPDATA%\\ClaudeOffice on Windows,
    ~/Library/Application Support/ClaudeOffice on a Mac."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/ClaudeOffice")
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ClaudeOffice")


def open_window(url: str) -> None:
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
        if time.time() - started > IDLE_EXIT_SECONDS and server.VIEWERS.idle_for() > IDLE_EXIT_SECONDS:
            httpd.shutdown()
            return


def main() -> None:
    global _has_console
    args = sys.argv[1:]
    if args[:1] == ["--hook"]:
        import claude_hook
        try:
            claude_hook.main()
        except Exception:
            pass
        sys.exit(0)
    if args[:1] == ["--install"]:
        _has_console = attach_console()
        import install_hooks
        rest = args[1:]
        project = None
        if "--project" in rest:
            i = rest.index("--project")
            project = rest[i + 1] if i + 1 < len(rest) else "."
        try:
            tell(install_hooks.install(project, "--uninstall" in rest))
        except Exception as e:
            tell(f"Couldn't update the Claude Code settings:\n{e}", error=True)
            sys.exit(1)
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
        tell(__doc__ or "")
        return
    run_app()


if __name__ == "__main__":
    main()
