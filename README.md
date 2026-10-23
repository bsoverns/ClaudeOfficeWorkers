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

**[⬇ Download ClaudeOffice-mac.zip (latest)](https://github.com/bsoverns/ClaudeOfficeWorkers/releases/latest/download/ClaudeOffice-mac.zip)**

For macOS 11 or newer. It runs on the Mac's own Python 3.9 or newer (if `python3` is missing, run
`xcode-select --install` once). Unzip it somewhere it can stay, e.g. `/Applications/ClaudeOffice-mac`, then:

1. The app isn't signed, so clear the download flag once in Terminal:
   `xattr -dr com.apple.quarantine /Applications/ClaudeOffice-mac` (use your folder's path).
2. Double-click **Connect Claude Code.command** (then restart open Claude Code sessions).
3. Open **ClaudeOffice.app**. It uses Chrome, Edge, Brave, Chromium or Vivaldi for its own
   window, or your default browser if none of those is installed.

Sixteen workers hang out in the break room (TV, couch, pool, ping pong, kitchen, vending
machine, arcade, a nap room with cots, smoking patio with a cat). When you give Claude a task, the
boss (Claude, at the big desk) pages a worker over the PA; they walk to the boss for a work
slip and head to a station: carpentry, blacksmith, dairy barn, beekeeper, bakery, greenhouse, pizzeria,
art studio, lumber yard, chem lab, server room or shipping. Everyone gets a turn before
anyone goes twice, and a session keeps the same worker and station for every task it
gives (as long as they're free). Each subagent gets its own random character, kept for the whole
session: an agent named in its description ("Neo: fix three bugs") or by the Agent tool's `name`
comes back as the same character every time (its slip reads "Tasha as Neo"), and a continued agent
keeps its character. Those links are saved with the office and freed when the session ends (done,
**Done ✓**, `/clear`, `/exit`, 12 hours). When Claude starts subagents, the session's worker becomes
team lead: they run a meeting (each lead takes their own chair at the table, chats with other
leads and now and then watches a training video on the whiteboard), page each helper to the meeting room, hand
them their slips there, and supervise until the helpers are done (a lead whose turn ends while
helpers are still out keeps waiting for them in the meeting; it only waits on you once the last
one is back). A failed tool sends the worker to the Troubleshooting desk (staffed by a
rubber duck); when Claude stops or needs permission, the worker waits in the mailroom,
a chime plays and the tab shows a red icon. Say "done" and they go back on break. The work slip
shows the session's name as the Claude app shows it (your rename, else the app's own title),
or your first prompt until the session has a name.

On break, people chat with whoever is nearby: short back-and-forth exchanges about fish in the
microwave, last night's game, the stock market, reply-all disasters, TPS reports and the
cover-sheet memo, being asked to come in on Saturday (and Sunday), and more. The break room TV
flips channels every 40 seconds (the match, a paternity-test talk show, a survey game show and
a soap opera), and the couch reacts to the big moments. Everyone walks around the furniture:
paths go around tables, counters and station equipment, and only step onto a couch, beanbag or
chair to sit on it.

Everything is drawn in code (no images or libraries) and runs on your own PC: prompts and
tool activity go only to the local server on `127.0.0.1`, never anywhere else.

## Cost and privacy

> **The office costs no tokens and adds nothing to your Claude usage.** It only listens: it
> never calls Claude or any other AI model, and Claude never sees anything it does.

| | What happens | Why it's free |
|---|---|---|
| 🎣 **Hooks** | Claude Code runs a small script for each event (prompt sent, tool used, stop, subagent start and end). | They're `command` hooks, the kind that just runs a program. Claude Code's `prompt` and `agent` hook types ask the model and cost tokens; the office uses neither. |
| 🤫 **Hook output** | The script prints nothing and always exits 0, even on errors. | For some events (like `UserPromptSubmit`) Claude Code adds a hook's output to Claude's context. No output means nothing is added. |
| ⚡ **Speed** | Every hook is `async` with a 5-second limit, and the post gives up after half a second. | Claude never waits on the office. If it isn't running, the post fails instantly and nothing happens. |
| 🏠 **Network** | The script posts the event to `http://127.0.0.1:<port>/api/hook`, your own PC. | No internet, no API keys, no telemetry, no update checks. The page loads no CDNs, fonts or images. |
| 📄 **Your files** | The script reads the end of the session's transcript (on disk) to find its name, and a subagent's small `.meta.json` for its task description. | Plain local file reads. Prompts and messages are trimmed to 2,000 characters and tool results are dropped before the post. |

What it does cost is a moment of CPU: each hook starts a short-lived Python process (or
`ClaudeOffice.exe --hook`). The office remembers its jobs in a local state file (see
[Settings](#settings-right-hand-panel)); nothing leaves your machine. To check for yourself, read
[src/claude_hook.py](src/claude_hook.py) (about 120 lines) and the hook list in
[src/install_hooks.py](src/install_hooks.py).

## Themes

Pick one on the clock-in screen; your pick becomes the default (change it under Settings).

- **Classic Office**: carpentry, blacksmith, dairy barn, beekeeper (hives, bees and honey; the
  keeper works a smoker in a veiled hat), bakery, greenhouse, pizzeria, art studio, lumber yard,
  chem lab, server room, shipping. Stations are random.
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
- **North Pole** (Christmas): elves with jingle-bell hats, Santa and Mrs. Claus, reindeer (one with
  a glowing red nose), gingerbread people, snowmen and ugly-sweater wearers (nobody's turban or
  hijab gets a hat or antlers). Stations are the Nice List, Sleigh Hangar, Tree Farm, Toy Repair,
  Cookie Kitchen, Chimney Drop, Snow Machine, Letters to Santa, the Yeti Cave, Toy Testing,
  Lights & Wiring and Gift Wrapping. Falling snow, string lights, stockings, a wreath, a tree in
  the boss's office, a snowman on the patio and Santa's sleigh across the moon; the boss wears
  a Santa hat, and the break room talk turns to Secret Santa and eggnog.
- **Pirate Cove**: pirates with bandanas, eyepatches and gold earrings, deckhands in striped
  shirts, buccaneers in tricorns, pirates with a parrot on the shoulder, a bearded captain and a
  few cursed skeleton pirates (nobody's turban or hijab gets a hat or bandana). Stations are the
  Treasure Map, Hoist the Sails, Bottle Post, Hull Patching, the Galley, the Cannon Deck, the
  Ship's Wheel, Parrot Review ("PEP 8! PEP 8!"), the Kraken, Walk the Plank, the Bilge Pump and
  the Cargo Hold. Jolly Roger bunting, a ship sailing past the window, and the patio becomes a
  beach with a palm tree and a treasure chest; the boss wears a captain's tricorn, and the break
  room talk turns to grog and buried treasure.
- **Stone Age**: cave people in spotted fur tunics with bones in their hair, hunters with fang
  necklaces and face paint, shamans in triceratops-skull caps, and coworkers in dinosaur and woolly
  mammoth onesies (nobody's turban or hijab gets a hood or skull cap). Real dinosaurs do the heavy
  lifting. Stations are the Stone Tablets, Pterodactyl Airlift, the Fossil Dig, Fire Support, the
  Stone Table, the Catapult, the Wheel (reinvented again), Cave Paintings, the T-Rex Den, Volcano
  Testing, Dino Power and Dino Express. A smoking volcano out the window, and the patio becomes a
  jungle with a dino egg nest; the boss wears a bone crown, and the break room talk turns to
  mammoth for lunch and who invented the wheel this time.
- **Hero HQ** (superheroes): eight heroes and eight villains (even roster ids are heroes, odd ones
  villains), each with a suit, cape, emblem and mask in their power's colors; villains wear a
  horned cowl (nobody's turban or hijab gets one). The chest emblem shows the power; the back of
  the cape shows the side, so you can tell them apart from behind: heroes have three white
  stripes, villains an all-seeing eye in a black triangle (`capeSign()`; on a wheelchair it sits
  on the cape hem below the seat, since the backrest hides the rest). Powers, one each: super strength, heat, flight,
  cold, telepathy, electricity, teleportation, psychokinesis, super speed, time, regeneration,
  shapeshifting, telekinesis, portals, invisibility and eye rays (`POWERS` in `index.html`; hover
  a worker to see their alias and power). Most of the break is the usual break-room stuff, but a
  hero and a villain who end up chatting usually trade corny superhero insults, and about a third
  of their chats end in a short duel on the spot: fire, ice, lightning, eye beams, portals, a time
  stop, a shapeshifter turning into their rival, fliers floating overhead. Heroes never fight
  heroes and villains never fight villains. When either one is paged the duel ends on the spot
  and they head to work. Powers also get them around: the teleporter and the portal maker
  blink to the end of long trips, the speedster runs 2.5x with afterimages, fliers glide along
  their path at 2x without a walking animation and the invisible one fades out while walking. Stations are the Gadget Lab, Suit
  Forge, Portal Gate, Hero Hotline, Data Vault, Bio Lab, Danger Room, Comic Press, Cape
  Cleaners, Containment, Hero Supercomputer and Evidence Locker. A night skyline with a
  searchlight out the window and star bunting on the walls; the boss wears a domino mask.
- **Dev Shop**: the same floor re-skinned as where dev work happens. Three extra characters live
  only here and never take work (the "Dev Shop cast" in `index.html`):
  - **Gary**, the office manager, wanders the office with his coffee, talks about his Porsche and
    complains that someone parked in his spot.
  - **The two Bobs**, consultants with glasses, suspenders and clipboards, always walk side by side.
    While anyone has a job, they shadow that worker and make mostly unflattering notes, following them
    to the help desk and the mailroom too; with several jobs they move on to the next worker about
    every 25 seconds. When the office is quiet, they grade whoever is on break: one minute late,
    leaving before six. They pick one worker per page load to adore and keep telling Gary about,
    which ends with them interviewing Gary until he slips away. Every 3 to 5 minutes they interview
    a nervous worker at the break room dining table. Nobody else sits there until they're done, and
    a new job ends the interview at once.
  - Workers out of the Bobs' earshot swap nervous chats about them.

Every theme also re-skins the three rooms that used to stay a plain office, with the same furniture
footprints so nobody walks differently. Troubleshooting room / meeting room / mailroom:

| Theme | Troubleshooting | Meeting room | Mailroom |
|---|---|---|---|
| Classic Office | help desk | whiteboard and table | pigeonholes |
| Dev Shop | on-call war room, red alert lamps, incident graph | stand-up with a kanban board and sticky notes | merge queue of PR envelopes and a CI light |
| Sci-Fi Station | repair bay with a sparking panel and a force field | bridge with a holo planet | cargo teleporter pad and pods |
| Haunted House | seance desk with a crystal ball and candles | candlelit banquet table | raven post with wax-sealed letters and a coffin crate |
| Neon City | hacker den with neon terminals | holo-conference with a pulsing neon table | drone drop-off pad with glowing parcels |
| North Pole | toy repair workbench | "Naughty or Nice" list table | letters to Santa and sacks of mail |
| Pirate Cove | ship's surgeon corner with bottles | captain's chart table with a treasure map | bottle post with a parrot |
| Stone Age | shaman's cave fire | stone circle round a flat rock table | carved tablets and a pterodactyl perch |
| Hero HQ | med bay with a heartbeat monitor and triage desk | team-up room with a hologram table and a truce scoreboard | distress signals and a signal lamp |

The rubber duck stays in every theme, usually in a matching hat.

The orange cat on the patio bench stays too, and has opinions. When nobody is sitting on its bench it now
and then thinks out loud in a thought bubble (puffy box, trail of little circles): lasagna, fish in the
microwave, world domination if only it had thumbs. The smokers and the stretcher don't count as company:
with the whole roster on break the patio is almost never empty, so only the bench matters. Sometimes,
right after the bench empties: "I thought they'd never leave." People in other themes never notice. In
Hero HQ the telepath (whoever has the `telepathy` power in `POWERS`, Maria) can hear it. When she is on
break on the patio with someone else out there (a hero if there is one, else whoever is smoking with her),
the two have a short chat about the talking cat (checked every 6 to 12 seconds, then at most once every
2.5 to 4 minutes; it has its own timer, so other chats can't crowd it out), and now and then the cat
answers with a smug thought. When she is out there while the cat thinks, she often mutters about it.
Lines: `CAT_THOUGHTS`, `CAT_TALKS` and `CAT_SOLO` in `index.html`.

Dev Shop, Sci-Fi, Haunted House, Neon City, North Pole, Pirate Cove, Stone Age and Hero HQ all send workers to the station that matches what Claude
is doing (each themed station sits in the same slot, e.g. GitHub = Wormhole = Branching Woods):

| Station | Work that sends a worker there |
|---|---|
| Azure DevOps | work items, `AB#123`, comments, linking PRs, `dev.azure.com`, ADO MCP tools |
| Azure Portal | `portal.azure.com`, `az` CLI, resource groups, key vaults, Azure SQL |
| GitHub | `gh`, `git push/pull/merge/rebase/commit`, branches, pull requests |
| Support Tickets | support tickets, incidents, outages, "broken", "not working" |
| SQL Server | `.sql` files, stored procedures, T-SQL, `sqlcmd` |
| DB Projects | dacpacs, `.sqlproj`, `sqlpackage`, publish profiles, scripted deployments |
| Implementation | rollouts, go-lives, onboarding, client/tenant setup, feature flags, env vars, config files (`appsettings`, `.config`, `.env`) |
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
(changes go through pull requests) and one that strips Claude Code session links from commit
messages (CI also fails a PR that has one); skip it if you won't change the code.

`src\install_hooks.py` connects Claude Code once for every project. Restart open Claude Code
sessions afterwards. For a PC without Python, build the standalone app (below) and copy the zip.

On a Mac (Python 3.9+ as `python3`): `python3 src/install_hooks.py`, then `python3 src/server.py`
and open http://127.0.0.1:8777/.

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

### Mac app

`scripts/build_mac.sh` builds `dist/ClaudeOffice-mac/ClaudeOffice.app` and
`dist/ClaudeOffice-mac.zip`. There's no PyInstaller: the app is a small bash launcher
(`package/mac/ClaudeOffice`) that finds `python3` (Homebrew first, then the system one) and runs
`src/app.py`, which ships inside the app with `index.html`. It runs on any machine with `python3`
and `zip`. `VERSION=2026.10.20.1 scripts/build_mac.sh` stamps a version. The app takes the same
arguments as the exe:

```
ClaudeOffice.app/Contents/MacOS/ClaudeOffice [--server [port] | --install [--project DIR] [--uninstall] | --hook | cmd <args>]
```

The hooks run `python3 .../ClaudeOffice.app/Contents/Resources/ClaudeOffice/claude_hook.py`, using
the stable `python3` path the launcher found (passed in `CLAUDE_OFFICE_PYTHON`), so a Homebrew
Python upgrade doesn't break them. Installing from source on a Mac (`python3 src/install_hooks.py`)
writes the same stable `python3` path when it is the Python you ran it with. Saved jobs and the window profile live in
`~/Library/Application Support/ClaudeOffice`. The app is unsigned, so Gatekeeper blocks it until
the quarantine flag is cleared (see Download).

### CI and releases

`.github/workflows/build.yml` runs on every pull request: it compiles the Python, builds the
exe with the same steps as `scripts\build.bat`, and smoke-tests it (starts the built server, sends one
Claude hook event through `ClaudeOffice.exe --hook`, and checks the job arrives with the right
work area). A macOS job runs `scripts/build_mac.sh` and the same smoke test through the app's
launcher. The two builds run in parallel and neither waits for the other; both zips are
attached to the run as artifacts. When a change is merged to `main`:

1. A first job stamps the version as `YYYY.M.D.<run number>`, for example `2026.10.19.7` (written to `VERSION.txt`).
2. Once both builds pass, a release job creates a GitHub Release tagged `v<version>` with `ClaudeOffice.zip` and
   `ClaudeOffice-mac.zip` attached; the release notes are generated from the pull requests merged
   since the last release, so give PRs clear titles.

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

`py tests\sim_hooks.py` simulates Claude Code sessions through the real hook script against a test
office on port 8790 (it starts one if needed) and checks session names on the slips and that a
team lead waits for its helpers in the meeting room, and that each subagent keeps its own
character. It prints `all passed` or the failures.

## Settings (right-hand panel)

Chime when someone waits, soft blips on start/finish, re-chime every 5 minutes while
anyone waits, and desktop notifications. Stored in the browser. **Done ✓** on a card ends
that task; **Find** highlights the worker. Hover or click a worker to see what they're up to.
A worker whose Claude has gone quiet for 5 minutes dozes at their station; jobs with no
news for 12 hours are sent home automatically. "Recently finished" says why each worker
went home (you said done, Done button, `/clear`, helper finished, 12 hours); it shows only
the last hour.

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
  app.py                 entry point of the standalone exe and the Mac app (window, --hook, --install, cmd)
scripts/                 scripts you run
  start.bat              starts the server and opens the page
  build.bat              builds dist/ClaudeOffice/ClaudeOffice.exe and dist/ClaudeOffice.zip
  build_mac.sh           builds dist/ClaudeOffice-mac/ClaudeOffice.app and dist/ClaudeOffice-mac.zip
package/                 shipped inside the zip next to the exe
  Connect Claude Code.bat, Disconnect Claude Code.bat
  mac/                   the Mac app's launcher, Info.plist and Connect/Disconnect .command files
tools/
  make_icon.py           draws office.ico for the build (office.icns with --icns)
tests/
  sim_hooks.py           simulated sessions through the hook against a test office on port 8790
docs/
  CONNECT_A_PROJECT.md   setup for a new PC, global or per-project, with a paste-in prompt
.github/                 CI build + release, PR auto-assign, CODEOWNERS
.githooks/               pre-push guard that refuses pushes to main; commit-msg strips session links
```

## How Claude events map

| Hook event | Effect |
|---|---|
| `UserPromptSubmit` | New job or resume; "done"/"thanks"/"task complete" ends it |
| `PreToolUse` | Working; bubble shows the tool |
| `PostToolUseFailure` | Troubleshooting desk (an interrupt → mailroom) |
| `Notification`, `Stop` | Mailroom, waiting on you. With helpers still out, `Stop` keeps the lead working in the meeting ("Waiting for N helpers") and an idle `Notification` is ignored; a permission request still goes to the mailroom |
| `SubagentStart` / `SubagentStop` | A helper is paged to the meeting room by the team lead / goes back on break. When the last helper is back and the lead's turn had ended, the lead waits on you in the mailroom (also if its helpers go quiet for 10 minutes, e.g. a lost `SubagentStop`) |
| `SessionEnd` | `/clear`, `/logout` or exiting at the prompt: back to the break room. Any other end (e.g. the app closing an idle session): keeps waiting until you say done |

All hooks are async and time-stamped, so the server ignores events that arrive out of order.

The slip title is the session's name: the hook reads the end of the session transcript
(`transcript_path`, up to 2 MB) for the last rename (`custom-title`), else the app's own title
(`ai-title`), and sends it as `session_title`. A rename shows on the next event. Without a name
the title is your first prompt; helpers are titled "<type> helper for: <session name>".

A subagent's name and task come from its description: the hook reads
`<session>/subagents/agent-<id>.meta.json` beside the transcript on each subagent event and sends
it as `agent_description` (with the file's `toolUseId` as `agent_tool_use_id`). The server matches
that id to the lead's own `Agent` call (its `name`, else a leading "Name:" in its `description`);
with no id yet it guesses the oldest call of that agent type, and drops the guessed name if the
description has no "Name:". Calls that never start are dropped after 10 minutes or at your next
prompt; a subagent's own `Agent` calls are never taken as the lead's. Named subagents are keyed by name, others
by agent id. A new subagent gets a random free character no live session has linked; if none is
left, one linked to another session's idle agent, then any free one; with nobody free it queues.
