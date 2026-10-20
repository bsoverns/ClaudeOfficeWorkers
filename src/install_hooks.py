r"""Connect Claude Code to the Claude Office (or disconnect it).

  py src\install_hooks.py              add the office hooks to ~/.claude/settings.json
  py src\install_hooks.py --uninstall  remove them again
  py src\install_hooks.py --print      just show the hooks JSON, change nothing
  py src\install_hooks.py --project C:\path\to\repo [--uninstall]
                                   only that project: writes <repo>/.claude/settings.local.json
                                   (Claude Code's personal, git-ignored settings file)

The standalone build does the same with `ClaudeOffice.exe --install [...]`; its hooks run
`ClaudeOffice.exe --hook` instead of Python, so the PC needs no Python.

Without --project, every Claude Code session on this PC reports to the office. The hook is
silent and always succeeds, so Claude works normally when the office isn't running.
A backup of the settings file is written next to it before any change. Other hooks you
already have are left alone; ours are recognised by claude_hook.py / ClaudeOffice --hook,
and installing either kind replaces the other.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")

# event -> (matcher or None, async). All async, so the office never slows Claude down;
# the hook sends a timestamp so the server ignores an event that arrives out of order.
EVENTS = {
    "UserPromptSubmit": (None, True),
    "PreToolUse": ("*", True),
    "PostToolUseFailure": ("*", True),
    "Notification": (None, True),
    "Stop": (None, True),
    "SubagentStart": (None, True),
    "SubagentStop": (None, True),
    "SessionEnd": (None, True),
}


def hook_command() -> str:
    """The command Claude Code runs: the exe itself when frozen, else python + claude_hook.py."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable.replace(chr(92), "/")}" --hook'
    # The Mac launcher passes the stable python3 path (e.g. /opt/homebrew/bin/python3) so a
    # Python upgrade doesn't break the hook.
    py = os.environ.get("CLAUDE_OFFICE_PYTHON") or sys.executable
    if not os.environ.get("CLAUDE_OFFICE_PYTHON") and sys.platform == "darwin":
        # Running from source: write the stable python3 path, not a versioned Homebrew Cellar one.
        stable = shutil.which("python3")
        if stable and os.path.realpath(stable) == os.path.realpath(sys.executable):
            py = stable
    py = py.replace("\\", "/")
    hook = os.path.join(HERE, "claude_hook.py").replace("\\", "/")
    return f'"{py}" "{hook}"'


def ours(group: dict) -> bool:
    for h in group.get("hooks", []):
        cmd = str(h.get("command", "")) if isinstance(h, dict) else ""
        if ("claude_hook.py" in cmd and "ClaudeOffice" in cmd) or ("ClaudeOffice" in cmd and "--hook" in cmd):
            return True
    return False


def office_hooks() -> dict:
    out = {}
    for ev, (matcher, is_async) in EVENTS.items():
        hook = {"type": "command", "command": hook_command(), "timeout": 5}
        if is_async:
            hook["async"] = True
        group = {"hooks": [hook]}
        if matcher:
            group = {"matcher": matcher, **group}
        out[ev] = [group]
    return out


def install(project: str | None = None, uninstall: bool = False) -> str:
    """Add (or remove) the office hooks. Returns a message for the user; raises on bad input."""
    path = SETTINGS
    if project:
        root = os.path.abspath(project)
        if not os.path.isdir(root):
            raise ValueError(f"No such folder: {root}")
        path = os.path.join(root, ".claude", "settings.local.json")
    lines = []
    settings: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)
        backup = f"{path}.bak-office-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, backup)
        lines.append(f"Backed up settings to {backup}")
    hooks = settings.setdefault("hooks", {})
    for ev in list(hooks):
        groups = [g for g in hooks[ev] if not (isinstance(g, dict) and ours(g))]
        if groups:
            hooks[ev] = groups
        else:
            del hooks[ev]
    if not uninstall:
        for ev, groups in office_hooks().items():
            hooks.setdefault(ev, []).extend(groups)
    if not hooks:
        settings.pop("hooks", None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    if uninstall:
        lines.append(f"Removed the office hooks from {path}.")
    else:
        lines.append(f"Installed office hooks for {len(EVENTS)} events in {path}")
        lines.append("New Claude Code sessions will report to the office (restart any that are open).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if "--print" in argv:
        print(json.dumps({"hooks": office_hooks()}, indent=2))
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
