# Claude Office Workers

An animated office that shows what Claude Code is doing, so you notice when it's done.

Sixteen workers hang out in the break room (TV, couch, pool, ping pong, kitchen, vending
machine, arcade, nap beanbag, smoking patio with a cat). When you give Claude a task, a
random worker walks to the boss (Claude, at the big desk) for a work slip and heads to a
station: carpentry, blacksmith, dairy barn, valet parking, bakery, greenhouse, pizzeria,
art studio, lumber yard, chem lab, server room or shipping. Everyone gets a turn before
anyone goes twice. A failed tool sends the worker to the Troubleshooting desk (staffed by a
rubber duck); when Claude stops or needs permission, the worker waits in the mailroom,
a chime plays and the tab shows a red icon. Say "done" and they go back on break.

Everything is drawn in code (no images or libraries) and runs on your own PC: prompts and
tool activity go only to the local server on `127.0.0.1`, never anywhere else.

## Get it

Requirements: Windows 10/11, Python 3.9+ (`py`), and Edge or Chrome. No packages to install.

```
git clone https://github.com/bsoverns/ClaudeOfficeWorkers.git
cd ClaudeOfficeWorkers
py install_hooks.py
start.bat
```

`install_hooks.py` connects Claude Code once for every project. Restart open Claude Code
sessions afterwards. For a PC without Python, build the standalone app (below) and copy the zip.

## Run it

Double-click `start.bat` (or `py server.py`), then open http://127.0.0.1:8777/ and click
**Clock in** once so the browser allows sound. Standard-library Python only; it listens on
127.0.0.1 only. Port: `py server.py 9000` or env `CLAUDE_OFFICE_PORT` (set the same
variable for Claude Code so the hook follows).

Tip: open it as its own window on a second screen, e.g. `msedge --app=http://127.0.0.1:8777/`.

## Standalone app (no Python on the target PC)

`build.bat` builds `dist\ClaudeOffice\ClaudeOffice.exe` and `dist\ClaudeOffice.zip`
(it installs PyInstaller, needed only on the PC that builds). `build/` and `dist/` are
git-ignored; rebuild rather than committing them. The exe is everything in one:

```
ClaudeOffice.exe                      open the office in its own window (Edge/Chrome app mode);
                                      quits ~1 minute after the window is closed
ClaudeOffice.exe --server [port]      server only, no window
ClaudeOffice.exe --install [--project C:\repo] [--uninstall]
ClaudeOffice.exe --hook               what Claude Code runs for each event
ClaudeOffice.exe cmd <office.py args> e.g. cmd demo, cmd list
```

The zip includes `Connect Claude Code.bat` / `Disconnect Claude Code.bat`. Installing exe
hooks replaces Python hooks and vice versa. Rebuild after changing any `.py` or `index.html`.

## Connect Claude Code

See [CONNECT_A_PROJECT.md](CONNECT_A_PROJECT.md): install the hooks once for every project
(`py install_hooks.py`) or per project with a paste-in prompt (`--project`).

## Test from a command prompt

```
py office.py start "Build the login page"
py office.py trouble -m "Tests failed"
py office.py working -a "Editing app.js"
py office.py wait -m "Your turn!"
py office.py done            (newest job; or give an id, or "all")
py office.py list
py office.py demo            (a 90-second show with three workers)
```

## Settings (right-hand panel)

Chime when someone waits, soft blips on start/finish, re-chime every 5 minutes while
anyone waits, and desktop notifications. Stored in the browser. **Done ✓** on a card ends
that task; **Find** highlights the worker. Hover or click a worker to see what they're up to.
A worker whose Claude has gone quiet for 5 minutes dozes at their station; jobs with no
news for 12 hours are sent home automatically. "Recently finished" says why each worker
went home (you said done, Done button, `/clear`, helper finished, 12 hours).

The office remembers its jobs in `%LOCALAPPDATA%\ClaudeOffice\state.json`, so restarting it
(or the exe quitting after its window closes) puts everyone back where they were.

## Files

| File | What it does |
|------|--------------|
| `server.py` | Office state, worker rotation, HTTP API (`/api/state` long-poll, `/api/hook`, `/api/cmd`) |
| `index.html` | The animated office and side panel (canvas, no libraries) |
| `claude_hook.py` | Claude Code hook: forwards trimmed events to the server; silent, always exits 0 |
| `install_hooks.py` | Adds/removes the hooks in `~/.claude/settings.json` or a project's `settings.local.json` |
| `office.py` | Command-line control for testing |
| `start.bat` | Starts the server and opens the page |
| `app.py` | Entry point of the standalone exe (window, `--hook`, `--install`, `cmd`) |
| `build.bat`, `make_icon.py` | Build the exe + zip; draw `office.ico` |
| `Connect Claude Code.bat`, `Disconnect Claude Code.bat` | Shipped in the zip: run the exe's installer |
| `CONNECT_A_PROJECT.md` | Setup for a new PC, global or per-project, with a paste-in prompt |
| `AGENTS.md` | Rules for agents (and people) changing this repo |

## How Claude events map

| Hook event | Effect |
|---|---|
| `UserPromptSubmit` | New job (title = your prompt) or resume; "done"/"thanks"/"task complete" ends it |
| `PreToolUse` | Working; bubble shows the tool |
| `PostToolUseFailure` | Troubleshooting desk (an interrupt → mailroom) |
| `Notification`, `Stop` | Mailroom, waiting on you |
| `SubagentStart` / `SubagentStop` | A helper worker joins / leaves |
| `SessionEnd` | `/clear`, `/logout` or exiting at the prompt: back to the break room. Any other end (e.g. the app closing an idle session): keeps waiting until you say done |

All hooks are async and time-stamped, so the server ignores events that arrive out of order.
