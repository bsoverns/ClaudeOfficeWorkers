# Setting up the Claude Office (any machine)

The office has two halves:

- **The office itself** (`server.py` + `index.html`): runs on the machine, shows the animation.
- **The hooks**: a few lines in Claude Code's settings that make each session report to the
  office. You install them **globally** (every project on that machine) or **per project**.

Both halves live on the same machine. Each machine gets its own copy.

---

## 0. Easiest: the standalone app (no Python needed)

Download `ClaudeOffice.zip` from the latest release
(<https://github.com/bsoverns/ClaudeOfficeWorkers/releases/latest>), or build it yourself with
`build.bat` (it lands in `dist\`). It's the whole office in one program.

1. Copy `ClaudeOffice.zip` to the PC and unzip it somewhere it can stay, e.g.
   `C:\Tools\ClaudeOffice\`. Keep the `_internal` folder next to the exe.
2. Double-click **`Connect Claude Code.bat`** once. That's the global install (2a below)
   pointing at the exe. Restart any open Claude Code sessions.
3. Double-click **`ClaudeOffice.exe`** whenever you want the office. It opens in its own
   window; click **Clock in** once for sound. Closing the window shuts it down about a
   minute later. (Pin the exe to the taskbar for one-click access.)

Per project instead of global: in that project, paste the 2b prompt but use
`"C:\Tools\ClaudeOffice\ClaudeOffice.exe" --install --project .` as the command.
Test without Claude: `ClaudeOffice.exe cmd demo` (all `office.py` commands work after `cmd`).
Undo: **`Disconnect Claude Code.bat`**.

If you move the folder, run `Connect Claude Code.bat` again. Windows SmartScreen or a
work antivirus may warn about an unsigned exe the first time; if IT blocks it, use the
Python version below instead.

---

## 1. Python version: get the files onto the machine

**Personal PC:** already done, in `C:\Sandbox\Games\ClaudeOfficeWorkers`.

**Work PC (or any new machine):**

1. Copy the whole `ClaudeOfficeWorkers` folder over (USB, OneDrive, zip, or git). You only
   need these files: `server.py`, `index.html`, `claude_hook.py`, `install_hooks.py`,
   `office.py`, `start.bat`, `README.md` and this file.
   Put it anywhere, e.g. `C:\Tools\ClaudeOfficeWorkers`. Nothing depends on the path:
   the installer writes whatever folder it is run from into the hooks.
2. Check Python 3.9 or newer is installed: `py --version` (or `python --version`).
   No packages are needed.
3. Start the office: double-click `start.bat`, then click **Clock in** in the browser.
4. Optional check: `py office.py demo` should send three workers across the office.

> Work machines: it only listens on `127.0.0.1` (nothing leaves the PC), and needs no
> admin rights or installs. If port 8777 is taken, see "Changing the port" below.

---

## 2a. Connect globally (recommended): every project, one time per machine

From a command prompt, in the office folder:

```
py install_hooks.py
```

That adds the hooks to `%USERPROFILE%\.claude\settings.json` (a backup is saved next to it
first; your other settings and hooks are kept). Restart any Claude Code sessions that were
already open. Done: every project on this machine now reports to the office.

Undo: `py install_hooks.py --uninstall`

If you ever **move the folder**, run `py install_hooks.py` again from the new place (it
replaces the old entries).

---

## 2b. Connect one project at a time

Use this instead of 2a when you only want some projects to report (e.g. on the work PC).
Open Claude Code in the project and paste the block below once. **Change the first line
to where the office folder is on that machine.**

```
My Claude Office is at: C:\Sandbox\Games\ClaudeOfficeWorkers

Connect this project to it. It's an animated office on this PC that shows when you are
working, stuck, or waiting on me.

1. Run: py "<office folder>\install_hooks.py" --project .
   It adds async hooks to .claude/settings.local.json (personal, git-ignored) that run
   claude_hook.py, which posts what you're doing to http://127.0.0.1:8777. The hook is
   silent, always exits 0, and does nothing if the office isn't running.
2. Check .claude/settings.local.json is ignored by git
   (git check-ignore -v .claude/settings.local.json). If not, add it to .gitignore.
   Don't commit it: it contains paths on this PC.
3. If the global hooks are also installed (look for claude_hook.py in
   %USERPROFILE%\.claude\settings.json), stop and tell me: the project hooks would make
   every event report twice.
4. Tell me to restart this session so the hooks load. After the restart, my next prompt
   should send a worker to the boss.
```

Undo for one project: `py "<office folder>\install_hooks.py" --project . --uninstall`

---

## 3. Optional: tell Claude about it (either setup)

Hooks do all the reporting; Claude doesn't need to know. If you want Claude to respect
"done" as the end of a task, add this to the project's `CLAUDE.md` (or your personal
`%USERPROFILE%\.claude\CLAUDE.md` to cover every project):

```
## Claude Office
- My sessions report to the Claude Office through hooks. Nothing to do while working.
- When I say "done", "thanks" or "task complete", the task is finished and my worker goes
  back to the break room. Don't start new work after that unless I ask.
- Never edit or remove the Claude Office hooks unless I ask.
```

---

## Changing the port

Default is 8777. To use another, e.g. 8790: set a user environment variable
`CLAUDE_OFFICE_PORT=8790` (Windows: Settings → "Edit environment variables for your
account"), then restart the office and Claude Code. The server, the hook and `office.py`
all read it. Open the page at `http://127.0.0.1:8790/` (`start.bat` opens 8777, so edit
the URL in it too).

---

## What you'll see

Pick a theme on the clock-in screen: **Classic Office**, **Dev Shop**, **Sci-Fi Station** or
**Haunted House**. In all but Classic, workers go to the station for the kind of work (Azure
DevOps, GitHub, SQL Server, Python…); see README.


| Claude is…                                 | The worker…                                     |
|--------------------------------------------|-------------------------------------------------|
| given a new prompt                         | is paged by the boss, gets a work slip, goes to a station (same worker for the same session) |
| using tools                                | works at the station; a bubble shows the tool ("Editing app.js") |
| hitting a failed tool or command           | queues at the Troubleshooting help desk          |
| asking permission, or finished its turn    | waits in the mailroom waving an envelope; chime + red tab icon |
| told "done" / "thanks", Done ✓, or `/clear` | celebrates and goes back to the break room      |
| starting subagents                         | becomes team lead in the meeting room; each helper is paged there for their slip |

## Quick reference

| Task | Command (run in the office folder) |
|---|---|
| Start the office | `start.bat` |
| Connect all projects | `py install_hooks.py` |
| Disconnect all | `py install_hooks.py --uninstall` |
| Connect one project | `py install_hooks.py --project C:\path\to\project` |
| Disconnect one project | `py install_hooks.py --project C:\path\to\project --uninstall` |
| See the hook JSON only | `py install_hooks.py --print` |
| Test without Claude | `py office.py demo` |
