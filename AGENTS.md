# AGENTS.md

Rules for agents (and people) working in this repo.

## What this is

Claude Office Workers: an animated office that shows what Claude Code sessions are doing.
`src/server.py` (Python standard library, `http.server`) holds the jobs and worker rotation and
serves `src/index.html`, a single canvas page with no libraries. Claude Code reaches it through
hooks that run `src/claude_hook.py` (or `ClaudeOffice.exe --hook`). See `README.md` (its Files section maps the folders).

## Commands

- Check: `py -m py_compile src/app.py src/server.py src/office.py src/install_hooks.py src/claude_hook.py tools/make_icon.py`
- Run: `py src/server.py 8790` (a spare port; see Testing), page at `http://127.0.0.1:8790/`
- Demo: `set CLAUDE_OFFICE_PORT=8790` then `py src/office.py demo`
- Build the exe: `scripts/build.bat` (output in `dist/`, git-ignored). CI (`.github/workflows/build.yml`)
  builds and smoke-tests it on every PR and publishes a GitHub Release on every merge to `main`;
  keep its build steps in step with `scripts/build.bat`.
- Build the Mac app: `scripts/build_mac.sh` (output in `dist/`; no PyInstaller, runs anywhere with
  `python3` and `zip`). CI builds and smoke-tests it on `macos-latest` and attaches the zip to the release;
  keep the CI step in step with `scripts/build_mac.sh`. Mac-only code paths check `sys.platform == "darwin"`.

## Testing

- The owner's real office runs on port 8777, and every Claude Code session on this PC posts
  to it, including yours. Test on another port so you don't mix test jobs into the real office.
- Simulate Claude by piping hook JSON into `src/claude_hook.py` with `CLAUDE_OFFICE_PORT` set.
  Write JSON with Python or a file, not shell echo: shells eat the backslashes in Windows paths.
- `py tests/sim_hooks.py` does that for session names, team leads waiting on helpers and subagent characters, on port
  8790 only (it starts a server there if none is running). Run it after changing the hook or `handle_hook`.
- Don't run `src/install_hooks.py` without `--project <scratch folder>` or `--print` unless asked:
  it changes `~/.claude/settings.json` for every session.

## Rules

- Standard library only for the office; PyInstaller is only for building. Ask before adding
  packages, frameworks, CDNs or a build step for the page.
- Hooks must never get in Claude's way: silent, always exit 0, short timeouts, async.
- Keep the API and the page in step: change an endpoint in `server.py`, update `index.html`
  and `office.py` in the same change. The roster and station list live in `server.py` (roster)
  and `index.html` `STATION_ORDER` (stations), which must match `STATIONS` in `server.py`.
  Work areas: `AREA_RULES` in `server.py` and `AREA_SLOT` in `index.html` must use the same keys.
  A theme (`THEMES` in `index.html`) is a set of 12 station definitions keyed by those slots
  (`STA` Classic, `DEV` Dev Shop, `SCIFI`, `HORROR`, `CYBER` Neon City, `XMAS` North Pole, `PIRATE` Pirate Cove, `STONE` Stone Age, `HERO` Hero HQ), plus optional
  `routed`, `costumes` (see `dress()`), `wash`, `decor`, `blocks` and `rooms` (skins for the troubleshooting room, meeting room
  and mailroom: `{trouble, meeting, mail}`, each with optional `back`/`fx`/`counter`|`table`/`duck`; assigned in the "Themed rooms" section, a missing entry means Classic, and furniture footprints must not change). Station draws use coordinates
  relative to the cell (x, y) and keep their equipment right of x + 92 (that area is blocked for walking).
- People walk on a grid (`FLOORS` minus `WALLS`, `FURNITURE`, station equipment and a theme's `blocks`), A* plus
  straightening in `findPath()`. When you draw new furniture or decor people could walk through, add
  its floor footprint to `FURNITURE` (or the theme's `blocks`). Rooms connect only through doorways: a gap
  between `FLOORS` rects is a wall, and an inner wall goes in `WALLS`; stepping onto a couch or cot never crosses one.
- `install_hooks.py` must stay idempotent and keep other people's hooks and settings.
- Every `<input>` needs a distinct `name=` and `autocomplete="off"`.
- The repo is public: no personal paths, tokens or prompts in commits, and no Claude Code session
  links (`Claude-Session:` lines) in commit messages: `.githooks/commit-msg` strips them and CI fails
  a PR that has one. Never commit `dist/`, `build/`, `.claude/` or settings backups.
- Base branch `main` (read "master" as `main`). **Never push to `main`**, not even a one-line
  fix: work on a feature branch named `YYYY-MM-DD_Short_Description` and open a PR. The owner
  is the only approver (`.github/CODEOWNERS` + the "Protect main" ruleset). An agent may
  squash-merge its own PR (`gh pr merge <n> --squash`) when the owner asked for it, in chat or in
  the ticket ("squash and merge"), and every CI check has passed. Then it pulls `main` and starts
  the next piece of work on a new branch. Otherwise it leaves the PR for the owner to merge.
  `.githooks/pre-push` refuses pushes to `main` (and `commit-msg` strips session links); enable them in each clone with
  `git config core.hooksPath .githooks`. Never bypass it (`--no-verify`).

## Documentation

Update `README.md` (and `docs/CONNECT_A_PROJECT.md` for setup changes) in the same change as the
code. Write for the owner reading it later.
