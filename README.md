# Claude Office Workers

[![Build](https://github.com/bsoverns/ClaudeOfficeWorkers/actions/workflows/build.yml/badge.svg)](https://github.com/bsoverns/ClaudeOfficeWorkers/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/bsoverns/ClaudeOfficeWorkers?label=download)](https://github.com/bsoverns/ClaudeOfficeWorkers/releases/latest)

An animated office that shows what Claude Code is doing, so you notice when it's done.

## Download

**[⬇ Download ClaudeOffice.zip (latest)](https://github.com/bsoverns/ClaudeOfficeWorkers/releases/latest/download/ClaudeOffice.zip)**

For 64-bit Windows, with no Python needed. Unzip it somewhere it can stay, double-click
**Connect Claude Code.bat** once (then restart open Claude Code sessions), and open
**ClaudeOffice.exe**. Every change merged to `main` builds a new release automatically; see
[all releases and their notes](https://github.com/bsoverns/ClaudeOfficeWorkers/releases).
`VERSION.txt` in the folder says which build you have.

> The exe isn't code-signed, so Windows SmartScreen may warn the first time. Click
> **More info → Run anyway**, or right-click the zip → **Properties** → tick **Unblock** before unzipping.

Sixteen workers hang out in the break room (TV, couch, pool, ping pong, kitchen, vending
machine, arcade, nap beanbag, smoking patio with a cat). When you give Claude a task, the
boss (Claude, at the big desk) pages a worker over the PA; they walk to the boss for a work
slip and head to a station: carpentry, blacksmith, dairy barn, valet parking, bakery, greenhouse, pizzeria,
art studio, lumber yard, chem lab, server room or shipping. Everyone gets a turn before
anyone goes twice, and a session keeps the same worker and station for every task it
gives (as long as they're free). When Claude starts subagents, the session's worker becomes
team lead: they run a meeting at the whiteboard, page each helper to the meeting room, hand
them their slips there, and supervise until the helpers are done. A failed tool sends the worker to the Troubleshooting desk (staffed by a
rubber duck); when Claude stops or needs permission, the worker waits in the mailroom,
a chime plays and the tab shows a red icon. Say "done" and they go back on break.

Everything is drawn in code (no images or libraries) and runs on your own PC: prompts and
tool activity go only to the local server on `127.0.0.1`, never anywhere else.

## Themes

Pick one on the clock-in screen; your pick becomes the default (change it under Settings).

- **Classic Office**: carpentry, blacksmith, dairy barn, valet parking, bakery, greenhouse,
  pizzeria, art studio, lumber yard, chem lab, server room, shipping. Stations are random.
- **Sci-Fi Station**: the staff become astronauts, aliens (including xenomorph-style ones), robots, cyborgs and space wizards with laser
  swords; stations are Mission Control, Orbital Cloud, Wormhole, Hull Breach, Data Core,
  Launch Pad, Engine Room, Xeno Lab, Alien Nest, Simulation Deck, Robot Bay and Cargo Bay.
  The boss wears a space helmet and a UFO drifts over the patio.
- **Haunted House**: Dracula, Frankenstein, the Wolfman, mummies, witches, skeletons, ghosts,
  zombies, slime monsters, demons and pumpkin-head scarecrows; stations are the Ticket Crypt, Storm Tower, Branching Woods, Cursed Junk, Witch's
  Cauldron, Gravedigging, Mad Lab, Snake Pit, the Dungeon, Potion Testing, Igor's Workshop and
  Coffin Shipping. Jack-o'-lanterns, cobwebs, fog and bats; the boss wears a witch's hat.
- **Neon City** (cyberpunk): netrunners with VR visors and data cables, street samurai with
  neon katanas, LED-mask punks whose masks cycle pixel faces, glitching holo-idols, corpo suits
  with AR monocles and briefcases, ripperdocs with chrome hands, drone couriers (a drone follows
  them) and androids with glowing seams. Stations are the Gig Board, Data Tower, Fork Alley,
  Ripperdoc Clinic, Data Vault, Drop Zone, Mod Garage, Snake Arcade, the Blackwall, Sim Dojo,
  Chop Shop and Surveillance. Rain, neon signs, a skyline window, a hover car; the boss wears
  an AR visor.
- **Dev Shop**: the same floor re-skinned as where dev work happens.

Dev Shop, Sci-Fi, Haunted House and Neon City all send workers to the station that matches what Claude
is doing (each themed station sits in the same slot, e.g. GitHub = Wormhole = Branching Woods):

| Station | Work that sends a worker there |
|---|---|
| Azure DevOps | work items, `AB#123`, comments, linking PRs, `dev.azure.com`, ADO MCP tools |
| Azure Portal | `portal.azure.com`, `az` CLI, resource groups, key vaults, Azure SQL |
| GitHub | `gh`, `git push/pull/merge/rebase/commit`, branches, pull requests |
| Support Tickets | support tickets, incidents, outages, "broken", "not working" |
| SQL Server | `.sql` files, stored procedures, T-SQL, `sqlcmd` |
| DB Projects | dacpacs, `.sqlproj`, `sqlpackage`, publish profiles, scripted deployments |
| Implementation | the Implementation project, appsettings / `.config`, client config, feature flags |
| Python | `.py` files, `python`, `pip` |
| Service Code | `*.Service` projects, Windows/worker/hosted services, legacy code (it's dark in there) |
| QA Test Lab | unit/integration tests, `pytest`, `dotnet test`, `npm test` |
| Hardware | printers, drivers, docks, USB, firmware |
| Tracking | time tracking, Taskmaskitator, status/daily reports, shipments |

The server scores those keywords from your prompt (strongest), the project folder, and each
tool call (file paths, commands, URLs, MCP tool names). A new prompt can move the worker
straight away; tool calls only move them once another area clearly leads and they've been at
their station 20 seconds, so they don't ping-pong. Until there's a clue, the worker uses
their usual station. Rules live in `AREA_RULES` in `server.py`.
Test a station: `py src\office.py start "Fix the sproc" --area sql`.

## Run from source

Requirements: Windows 10/11, Python 3.9+ (`py`), and Edge or Chrome. No packages to install.

```
git clone https://github.com/bsoverns/ClaudeOfficeWorkers.git
cd ClaudeOfficeWorkers
git config core.hooksPath .githooks
py src\install_hooks.py
scripts\start.bat
```

`git config core.hooksPath .githooks` turns on a guard that refuses pushes to `main`
(changes go through pull requests); skip it if you won't change the code.

`src\install_hooks.py` connects Claude Code once for every project. Restart open Claude Code
sessions afterwards. For a PC without Python, build the standalone app (below) and copy the zip.

## Run it

Double-click `scripts\start.bat` (or `py src\server.py`), then open http://127.0.0.1:8777/ and click
**Clock in** once so the browser allows sound. Standard-library Python only; it listens on
127.0.0.1 only. Port: `py src\server.py 9000` or env `CLAUDE_OFFICE_PORT` (set the same
variable for Claude Code so the hook follows).

Tip: open it as its own window on a second screen, e.g. `msedge --app=http://127.0.0.1:8777/`.

## Standalone app (no Python on the target PC)

`scripts\build.bat` builds `dist\ClaudeOffice\ClaudeOffice.exe` and `dist\ClaudeOffice.zip`
(it installs PyInstaller, needed only on the PC that builds). `build/` and `dist/` are
git-ignored; rebuild rather than committing them.

### CI and releases

`.github/workflows/build.yml` runs on every pull request: it compiles the Python, builds the
exe with the same steps as `scripts\build.bat`, and smoke-tests it (starts the built server, sends one
Claude hook event through `ClaudeOffice.exe --hook`, and checks the job arrives with the right
work area). The zip is attached to the run as an artifact. When a change is merged to `main`
it also:

1. Stamps the version as `YYYY.M.D.<run number>`, for example `2026.10.19.7` (written to `VERSION.txt`).
2. Creates a GitHub Release tagged `v<version>` with `ClaudeOffice.zip` attached; the release
   notes are generated from the pull requests merged since the last release, so give PRs clear titles.

`.github/workflows/auto-assign.yml` assigns every new PR to the repository owner.

The exe is everything in one:

```
ClaudeOffice.exe                      open the office in its own window (Edge/Chrome app mode);
                                      quits ~1 minute after the window is closed
ClaudeOffice.exe --server [port]      server only, no window
ClaudeOffice.exe --install [--project C:\repo] [--uninstall]
ClaudeOffice.exe --hook               what Claude Code runs for each event
ClaudeOffice.exe cmd <src\office.py args> e.g. cmd demo, cmd list
```

The zip includes `Connect Claude Code.bat` / `Disconnect Claude Code.bat`. Installing exe
hooks replaces Python hooks and vice versa. Rebuild after changing anything in `src/`.

## Connect Claude Code

See [docs/CONNECT_A_PROJECT.md](docs/CONNECT_A_PROJECT.md): install the hooks once for every project
(`py src\install_hooks.py`) or per project with a paste-in prompt (`--project`).

## Test from a command prompt

```
py src\office.py start "Build the login page"
py src\office.py trouble -m "Tests failed"
py src\office.py working -a "Editing app.js"
py src\office.py wait -m "Your turn!"
py src\office.py done            (newest job; or give an id, or "all")
py src\office.py list
py src\office.py demo            (a 90-second show with three workers)
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

## Contributing

Anyone can propose a change: fork the repo, push a branch, and open a pull request against
`main`. `.github/CODEOWNERS` makes @bsoverns the owner of every file, so every PR requests
their review, and the "Protect main" ruleset only lets a PR merge once the code owner has
approved it. Nobody pushes to `main` directly.

## License

[MIT](LICENSE): use it, change it, share it, sell it; just keep the copyright notice. No warranty.

## Files

```
README.md, LICENSE       this page and the MIT license
AGENTS.md, CLAUDE.md     rules for agents working in the repo (CLAUDE.md just imports AGENTS.md)
src/                     the program
  server.py              office state, worker rotation, HTTP API (/api/state long-poll, /api/hook, /api/cmd)
  index.html             the animated office, themes and side panel (canvas, no libraries)
  claude_hook.py         Claude Code hook: forwards trimmed events to the server; silent, always exits 0
  install_hooks.py       adds/removes the hooks in ~/.claude/settings.json or a project's settings.local.json
  office.py              command-line control for testing
  app.py                 entry point of the standalone exe (window, --hook, --install, cmd)
scripts/                 batch files you run
  start.bat              starts the server and opens the page
  build.bat              builds dist/ClaudeOffice/ClaudeOffice.exe and dist/ClaudeOffice.zip
package/                 shipped inside the zip next to the exe
  Connect Claude Code.bat, Disconnect Claude Code.bat
tools/
  make_icon.py           draws office.ico for the build
docs/
  CONNECT_A_PROJECT.md   setup for a new PC, global or per-project, with a paste-in prompt
.github/                 CI build + release, PR auto-assign, CODEOWNERS
.githooks/               pre-push guard that refuses pushes to main
```

## How Claude events map

| Hook event | Effect |
|---|---|
| `UserPromptSubmit` | New job (title = your prompt) or resume; "done"/"thanks"/"task complete" ends it |
| `PreToolUse` | Working; bubble shows the tool |
| `PostToolUseFailure` | Troubleshooting desk (an interrupt → mailroom) |
| `Notification`, `Stop` | Mailroom, waiting on you |
| `SubagentStart` / `SubagentStop` | A helper is paged to the meeting room by the team lead / goes back on break |
| `SessionEnd` | `/clear`, `/logout` or exiting at the prompt: back to the break room. Any other end (e.g. the app closing an idle session): keeps waiting until you say done |

All hooks are async and time-stamped, so the server ignores events that arrive out of order.
