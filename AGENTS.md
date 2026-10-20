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

## Testing

- The owner's real office runs on port 8777, and every Claude Code session on this PC posts
  to it, including yours. Test on another port so you don't mix test jobs into the real office.
- Simulate Claude by piping hook JSON into `src/claude_hook.py` with `CLAUDE_OFFICE_PORT` set.
  Write JSON with Python or a file, not shell echo: shells eat the backslashes in Windows paths.
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
  (`STA` Classic, `DEV` Dev Shop, `SCIFI`, `HORROR`, `CYBER` Neon City, `XMAS` North Pole), plus optional
  `routed`, `costumes` (see `dress()`), `wash`, `decor` and `blocks`. Station draws use coordinates
  relative to the cell (x, y) and keep their equipment right of x + 92 (that area is blocked for walking).
- People walk on a grid (`FLOORS` minus `WALLS`, `FURNITURE`, station equipment and a theme's `blocks`), A* plus
  straightening in `findPath()`. When you draw new furniture or decor people could walk through, add
  its floor footprint to `FURNITURE` (or the theme's `blocks`). Rooms connect only through doorways: a gap
  between `FLOORS` rects is a wall, and an inner wall goes in `WALLS`; stepping onto a couch or cot never crosses one.
- `install_hooks.py` must stay idempotent and keep other people's hooks and settings.
- Every `<input>` needs a distinct `name=` and `autocomplete="off"`.
- The repo is public: no personal paths, tokens or prompts in commits. Never commit `dist/`,
  `build/` or settings backups.
- Base branch `main` (read "master" as `main`). **Never push to `main`**, not even a one-line
  fix: work on a feature branch named `YYYY-MM-DD_Short_Description` and open a PR; the owner
  merges and is the only approver (`.github/CODEOWNERS` + the "Protect main" ruleset).
  `.githooks/pre-push` refuses pushes to `main`; enable it in each clone with
  `git config core.hooksPath .githooks`. Never bypass it (`--no-verify`).

## Documentation

Update `README.md` (and `docs/CONNECT_A_PROJECT.md` for setup changes) in the same change as the
code. Write for the owner reading it later.
