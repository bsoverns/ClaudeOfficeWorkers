r"""Connect Cursor to the Cursor office (or disconnect it). install_hooks.py does the same for Claude Code.

  py src\install_cursor_hooks.py              add the office hooks to ~/.cursor/hooks.json
  py src\install_cursor_hooks.py --uninstall  remove them again
  py src\install_cursor_hooks.py --print      just show the hooks JSON, change nothing
  py src\install_cursor_hooks.py --project C:\path\to\repo [--uninstall]
                                   only that project: writes <repo>/.cursor/hooks.json

The standalone build does the same with `CursorOffice.exe --install [...]`; its hooks run
`CursorOffice.exe --cursor-hook` instead of Python, so the PC needs no Python.

A backup of the file is written next to it before any change. Other hooks you already have are
left alone; ours are recognised by cursor_hook.py / --cursor-hook, and installing either kind
replaces the other.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS_FILE = os.path.join(os.path.expanduser("~"), ".cursor", "hooks.json")

# Only events that can't block Cursor. Never add a permission hook (preToolUse, subagentStart,
# beforeShellExecution, beforeMCPExecution, beforeReadFile, beforeTabFileRead) here: bad output blocks the action.
EVENTS = ("beforeSubmitPrompt", "postToolUse", "postToolUseFailure", "stop", "sessionEnd")


def hook_command() -> str:
    """The command Cursor runs: the exe itself when frozen, else python + cursor_hook.py. The
    Cursor desktop app runs hook commands through PowerShell on Windows, and PowerShell needs
    the & to run a quoted path."""
    prefix = "& " if os.name == "nt" else ""
    if getattr(sys, "frozen", False):
        return f'{prefix}"{sys.executable.replace(chr(92), "/")}" --cursor-hook'
    py = (os.environ.get("CLAUDE_OFFICE_PYTHON") or sys.executable).replace("\\", "/")
    hook = os.path.join(HERE, "cursor_hook.py").replace("\\", "/")
    return f'{prefix}"{py}" "{hook}"'


def ours(entry: object) -> bool:
    cmd = str(entry.get("command", "")) if isinstance(entry, dict) else ""
    return "cursor_hook.py" in cmd or "--cursor-hook" in cmd


def office_hooks() -> dict:
    return {ev: [{"command": hook_command(), "timeout": 5}] for ev in EVENTS}


def install(project: str | None = None, uninstall: bool = False) -> str:
    """Add (or remove) the office hooks. Returns a message for the user; raises on bad input."""
    path = HOOKS_FILE
    if project:
        root = os.path.abspath(project)
        if not os.path.isdir(root):
            raise ValueError(f"No such folder: {root}")
        path = os.path.join(root, ".cursor", "hooks.json")
    lines = []
    config: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        backup = f"{path}.bak-office-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, backup)
        lines.append(f"Backed up hooks to {backup}")
    config.setdefault("version", 1)
    hooks = config.setdefault("hooks", {})
    for ev in list(hooks):
        entries = [e for e in hooks[ev] if not ours(e)]
        if entries:
            hooks[ev] = entries
        else:
            del hooks[ev]
    if not uninstall:
        for ev, entries in office_hooks().items():
            hooks.setdefault(ev, []).extend(entries)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    if uninstall:
        lines.append(f"Removed the office hooks from {path}.")
    else:
        lines.append(f"Installed office hooks for {len(EVENTS)} events in {path}")
        lines.append("Cursor picks them up when the file is saved; restart Cursor if nothing shows up.")
        if project:
            lines.append("Don't commit this file: it holds paths from this PC. Add .cursor/hooks.json to .gitignore.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if "--print" in argv:
        print(json.dumps({"version": 1, "hooks": office_hooks()}, indent=2))
        return
    project = None
    if "--project" in argv:
        i = argv.index("--project")
        if i + 1 >= len(argv):
            sys.exit("--project needs the project folder")
        project = argv[i + 1]
    try:
        print(install(project, "--uninstall" in argv))
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
