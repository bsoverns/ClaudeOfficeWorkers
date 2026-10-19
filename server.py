"""Claude Office Workers: a tiny local server that turns Claude Code activity into an
animated office.

Run:   py server.py [port]          (default 8777, or env CLAUDE_OFFICE_PORT)
Open:  http://127.0.0.1:8777/

Claude Code reports in through claude_hook.py (wired up by install_hooks.py), which
POSTs each hook payload to /api/hook. office.py sends manual commands to /api/cmd.
The page long-polls /api/state and does all the animation itself.

Standard library only. Binds to 127.0.0.1, so nothing outside this PC can reach it.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
RESOURCES = getattr(sys, "_MEIPASS", HERE)   # where index.html lives (bundled in the exe)
DEFAULT_PORT = 8777
EXPIRE_HOURS = 12      # a job with no news for this long is sent home
RECENT_MAX = 12        # finished jobs kept for the "Recently finished" list
LONG_POLL_SECONDS = 25

# The staff. The page draws them from these fields, so this is the only list.
# mobility: "" | "wheelchair" | "crutches" | "cane". smoker: may take smoke breaks.
ROSTER = [
    {"name": "Marcus", "skin": "#7a4a2a", "hair": "#16110d", "hairStyle": "fade", "beard": True,
     "shirt": "#2f6fd6", "pants": "#273042"},
    {"name": "Priya", "skin": "#b57a4f", "hair": "#120d0a", "hairStyle": "braid",
     "shirt": "#e8762d", "pants": "#3a2a52", "skirt": True},
    {"name": "Wei", "skin": "#efcfa8", "hair": "#141414", "hairStyle": "short", "glasses": True,
     "shirt": "#3c9a5f", "pants": "#2b2b2b"},
    {"name": "Haruto", "skin": "#f2d4b8", "hair": "#1d1a19", "hairStyle": "spiky",
     "shirt": "#d64545", "pants": "#30364a", "mobility": "crutches", "smoker": True},
    {"name": "Maria", "skin": "#c8915f", "hair": "#2a1a10", "hairStyle": "ponytail",
     "shirt": "#c2357a", "pants": "#2c3e66", "smoker": True},
    {"name": "Jake", "skin": "#f6d3b8", "hair": "#b5541c", "hairStyle": "short", "beard": True,
     "shirt": "#9b2d2d", "plaid": True, "pants": "#3b4a6b", "smoker": True},
    {"name": "Tasha", "skin": "#4b2d1c", "hair": "#120b08", "hairStyle": "afro",
     "shirt": "#7b4bc4", "pants": "#22252e", "mobility": "wheelchair"},
    {"name": "Raj", "skin": "#a76b3e", "hair": "#e35d2a", "hairStyle": "turban", "beard": True,
     "shirt": "#f2f2f2", "pants": "#2d3a4a"},
    {"name": "Emily", "skin": "#fbe1cc", "hair": "#e7c25a", "hairStyle": "bob",
     "shirt": "#38a3a5", "pants": "#3a3a48", "skirt": True},
    {"name": "Kenji", "skin": "#ecc9a3", "hair": "#cfcfcf", "hairStyle": "balding", "glasses": True,
     "shirt": "#5a6b7d", "pants": "#2a2a2a", "mobility": "cane"},
    {"name": "Mei", "skin": "#f3d5b0", "hair": "#0f0c0b", "hairStyle": "bun",
     "shirt": "#f2c14e", "pants": "#3a3a3a"},
    {"name": "Jamal", "skin": "#5c3a22", "hair": "#120c08", "hairStyle": "locs",
     "shirt": "#e0a030", "pants": "#4a3b2a", "smoker": True},
    {"name": "Rosa", "skin": "#c48a5a", "hair": "#9a9a9a", "hairStyle": "curly", "glasses": True,
     "shirt": "#2a9d8f", "pants": "#5b3d61", "skirt": True},
    {"name": "Sam", "skin": "#f4d7c4", "hair": "#e86aa8", "hairStyle": "pixie",
     "shirt": "#3d405b", "pants": "#22252e", "mobility": "wheelchair"},
    {"name": "Fatima", "skin": "#b98458", "hair": "#2f5d8a", "hairStyle": "hijab",
     "shirt": "#8ab17d", "pants": "#3a3550", "skirt": True},
    {"name": "Arjun", "skin": "#946038", "hair": "#16110d", "hairStyle": "short", "mustache": True,
     "shirt": "#4f5bd5", "pants": "#2b2b35", "smoker": True},
]
for _i, _w in enumerate(ROSTER):
    _w["id"] = _i
    _w.setdefault("mobility", "")

# Work stations, in the order the page lays them out (4 columns x 3 rows).
STATIONS = ["workbench", "forge", "dairy", "valet", "bakery", "garden",
            "pizza", "easel", "lumber", "lab", "servers", "packing"]

# A prompt that is only this means "we're finished": the worker goes back to the break room.
DONE_RE = re.compile(
    r"^\s*(?:task\s+(?:is\s+)?(?:complete|completed|done|finished)|all\s+done|done|complete|"
    r"finished|we'?re\s+done|that'?s\s+all|thanks?(?:\s+you)?|thank\s+you|thx|ty)\s*[.!]*\s*$",
    re.I)

# SessionEnd reasons that mean you finished the session on purpose.
SESSION_END_DONE = {"clear": "you cleared the session", "logout": "you logged out",
                    "prompt_input_exit": "you closed the session"}

PUBLIC_JOB_KEYS = ("id", "title", "project", "kind", "parent", "status", "message", "activity",
                   "worker", "station", "created", "updated", "prompt")


PASTE_RE = re.compile(r"<pasted_content\b[^>]*>(.*?)(?:</pasted_content>|\Z)", re.S | re.I)
TAG_RE = re.compile(r"</?[A-Za-z][\w:-]*(?:\s[^<>]*)?/?>")
LINE_MARK_RE = re.compile(r"^\s*(?:#{1,6}\s*|>\s*|[-*+]\s+|\d+[.)]\s+)")


def plain_text(text: object) -> str:
    """Markup-free one-liner for a slip or bubble: drops tags Claude Code wraps around
    prompts (e.g. <pasted_content>) and Markdown (#, **, `, list bullets, links)."""
    text = TAG_RE.sub(" ", str(text or ""))
    text = " ".join(LINE_MARK_RE.sub("", line) for line in text.splitlines())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*|__|~~|`+", "", text)
    return " ".join(text.split())


def prompt_title(prompt: object) -> str:
    """What a prompt is about: your own words if you typed any, else the start of what you pasted."""
    prompt = str(prompt or "")
    own = plain_text(PASTE_RE.sub(" ", prompt))
    if own:
        return own
    for m in PASTE_RE.finditer(prompt):
        pasted = plain_text(m.group(1))
        if pasted:
            return pasted
    return ""


def clip(text: object, n: int) -> str:
    """One line, collapsed whitespace, at most n characters."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def describe_tool(name: str, inp: object) -> str:
    """A short, human description of a Claude Code tool call for the speech bubble."""
    inp = inp if isinstance(inp, dict) else {}

    def base(p: object) -> str:
        return os.path.basename(str(p or "").rstrip("\\/"))

    if name in ("Bash", "PowerShell"):
        return "$ " + clip(inp.get("command"), 44)
    if name == "Read":
        return "Reading " + base(inp.get("file_path"))
    if name in ("Edit", "MultiEdit"):
        return "Editing " + base(inp.get("file_path"))
    if name == "Write":
        return "Writing " + base(inp.get("file_path"))
    if name == "NotebookEdit":
        return "Editing a notebook"
    if name in ("Grep", "Glob"):
        return "Searching " + clip(inp.get("pattern"), 30)
    if name == "WebSearch":
        return "Googling " + clip(inp.get("query"), 30)
    if name == "WebFetch":
        return "Reading the web"
    if name in ("Agent", "Task"):
        return "Briefing a helper"
    if name == "TodoWrite":
        return "Updating the to-do list"
    if name.startswith("mcp__"):
        return "Using " + name.split("__")[-1].replace("_", " ")
    return "Using " + (name or "a tool")


class Office:
    """All jobs and the worker rotation. Every method takes self.lock."""

    def __init__(self) -> None:
        self.lock = threading.Condition()
        self.rev = 1
        self.jobs: dict[str, dict] = {}
        self.seq = 0
        self.used: set[int] = set()            # workers who have had a turn this rotation
        self.recent_stations: deque[str] = deque(maxlen=6)
        self.recent: list[dict] = []
        self.closed: set[str] = set()          # sessions marked done while their turn finishes
        self.cli_n = 0
        self.state_path = ""                   # set by load(); empty means don't save

    # ---- internals (caller holds the lock) -------------------------------------------
    def _bump(self) -> None:
        self.rev += 1
        self.lock.notify_all()
        self._save()

    # ---- saved state, so restarting the office keeps everyone where they were ----------
    def _save(self) -> None:
        if not self.state_path:
            return
        data = {"jobs": self.jobs, "seq": self.seq, "used": sorted(self.used), "recent": self.recent,
                "closed": sorted(self.closed), "cli_n": self.cli_n}
        try:
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def load(self, path: str) -> None:
        """Remember jobs in path from now on, starting from what was saved there."""
        with self.lock:
            self.state_path = path
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                return
            self.jobs = {k: v for k, v in (data.get("jobs") or {}).items() if isinstance(v, dict)}
            self.seq = int(data.get("seq") or 0)
            self.used = set(data.get("used") or [])
            self.recent = list(data.get("recent") or [])[:RECENT_MAX]
            self.closed = set(data.get("closed") or [])
            self.cli_n = int(data.get("cli_n") or 0)

    def _busy(self) -> set[int]:
        return {j["worker"] for j in self.jobs.values() if j["worker"] is not None}

    def _pick_worker(self) -> int | None:
        """Random free worker who hasn't had a turn yet; once everyone has, start a new round."""
        busy = self._busy()
        free = [w["id"] for w in ROSTER if w["id"] not in busy]
        if not free:
            return None
        fresh = [w for w in free if w not in self.used]
        if not fresh:
            self.used = set(busy)
            fresh = free
        pick = random.choice(fresh)
        self.used.add(pick)
        return pick

    def _pick_station(self) -> str:
        counts = {s: 0 for s in STATIONS}
        for j in self.jobs.values():
            if j["station"] in counts:
                counts[j["station"]] += 1
        low = min(counts.values())
        options = [s for s, c in counts.items() if c == low]
        prefer = [s for s in options if s not in self.recent_stations]
        pick = random.choice(prefer or options)
        self.recent_stations.append(pick)
        return pick

    def _staff(self, job: dict) -> None:
        if job["worker"] is None:
            job["worker"] = self._pick_worker()
            if job["worker"] is not None:
                job["station"] = self._pick_station()

    def _new_job(self, jid: str, title: str, project: str = "", kind: str = "main",
                 parent: str | None = None, ts: float | None = None) -> dict:
        now = time.time()
        self.seq += 1
        job = {"id": jid, "title": clip(title, 120) or "(untitled task)", "project": clip(project, 40),
               "kind": kind, "parent": parent, "status": "working", "message": "", "activity": "",
               "prompt": "", "worker": None, "station": None, "created": now, "updated": now,
               "status_ts": ts or now, "seq": self.seq}
        self._staff(job)
        self.jobs[jid] = job
        return job

    def _set_status(self, job: dict, status: str, message: str | None = None,
                    ts: float | None = None) -> None:
        """Change status unless a newer event already did (async hooks can arrive late)."""
        job["updated"] = time.time()
        ts = ts or time.time()
        if ts < job["status_ts"]:
            return
        job["status"] = status
        job["status_ts"] = ts
        if message is not None:
            job["message"] = clip(message, 200)

    def _finish(self, jid: str, reason: str) -> None:
        """Send the job's worker home. reason shows in "Recently finished" so you can tell why."""
        job = self.jobs.pop(jid, None)
        if not job:
            return
        for child in [j for j in self.jobs.values() if j["parent"] == jid]:
            self._finish(child["id"], reason)
        self.recent.insert(0, {"id": job["id"], "title": job["title"], "project": job["project"],
                               "worker": job["worker"], "created": job["created"],
                               "finished": time.time(), "reason": reason})
        del self.recent[RECENT_MAX:]
        for queued in sorted(self.jobs.values(), key=lambda j: j["seq"]):
            if queued["worker"] is None:
                self._staff(queued)
                if queued["worker"] is None:
                    break

    def _resolve(self, jid: str) -> dict | None:
        if jid and jid != "last":
            return self.jobs.get(jid)
        return max(self.jobs.values(), key=lambda j: j["seq"], default=None)

    # ---- Claude Code hooks ------------------------------------------------------------
    def handle_hook(self, p: dict) -> None:
        ev = str(p.get("hook_event_name") or "")
        sid = str(p.get("session_id") or "")
        if not sid:
            return
        ts = p.get("ts") if isinstance(p.get("ts"), (int, float)) else time.time()
        cwd = str(p.get("cwd") or "")
        project = os.path.basename(cwd.rstrip("\\/")) if cwd else ""
        agent_id = str(p.get("agent_id") or "")
        with self.lock:
            job = self.jobs.get(sid)
            if ev == "UserPromptSubmit":
                prompt = prompt_title(p.get("prompt"))
                if DONE_RE.match(prompt):
                    if job:
                        self._finish(sid, f'you said "{prompt}"')
                    self.closed.add(sid)
                else:
                    self.closed.discard(sid)
                    if not job:
                        job = self._new_job(sid, prompt, project, ts=ts)
                    elif job["title"].startswith("(picking up"):
                        job["title"] = clip(prompt, 120)
                    job["prompt"] = clip(prompt, 200)
                    job["activity"] = "Reading your message"
                    self._set_status(job, "working", "", ts)
            elif ev == "PreToolUse":
                if sid in self.closed:
                    return
                target = self.jobs.get(f"{sid}:{agent_id}") if agent_id else None
                if target is None:
                    if not job:
                        job = self._new_job(sid, "(picking up where we left off)", project, ts=ts)
                    target = job
                target["activity"] = describe_tool(str(p.get("tool_name") or ""), p.get("tool_input"))
                self._set_status(target, "working", "", ts)
            elif ev == "PostToolUseFailure":
                target = (self.jobs.get(f"{sid}:{agent_id}") if agent_id else None) or job
                if not target:
                    return
                if p.get("is_interrupt"):
                    self._set_status(target, "waiting", "You stopped me — what next?", ts)
                else:
                    err = clip(p.get("error") or "", 120) or "A tool failed"
                    self._set_status(target, "trouble", err, ts)
            elif ev == "Notification":
                if not job or sid in self.closed:
                    return
                self._set_status(job, "waiting", plain_text(p.get("message")) or "Waiting on you", ts)
            elif ev == "Stop":
                if not job or sid in self.closed:
                    return
                last = clip(plain_text(p.get("last_assistant_message")), 140)
                self._set_status(job, "waiting", last or "Finished — your turn!", ts)
                job["activity"] = ""
            elif ev == "SubagentStart":
                if not agent_id or sid in self.closed:
                    return
                kind = str(p.get("agent_type") or "helper")
                parent_title = job["title"] if job else ""
                title = f"{kind} helper" + (f" for: {parent_title}" if parent_title else "")
                if f"{sid}:{agent_id}" not in self.jobs:
                    self._new_job(f"{sid}:{agent_id}", title, project, kind="helper",
                                  parent=sid if job else None, ts=ts)
            elif ev == "SubagentStop":
                self._finish(f"{sid}:{agent_id}", "helper finished")
            elif ev == "SessionEnd":
                # Only an end you chose (/clear, /logout, /exit or Ctrl+C at the prompt) sends the
                # worker home. Anything else (an app closing or recycling an idle session) keeps
                # them waiting until you say done, press Done, or 12 hours pass.
                reason = str(p.get("reason") or "")
                if reason in SESSION_END_DONE:
                    self._finish(sid, SESSION_END_DONE[reason])
                    self.closed.discard(sid)
                elif job:
                    self._set_status(job, "waiting", "Session closed — still waiting on you", ts)
                    job["activity"] = ""
                else:
                    return
            else:
                return
            self._bump()

    # ---- manual commands (office.py / the page) ---------------------------------------
    def handle_cmd(self, p: dict) -> dict:
        cmd = str(p.get("cmd") or "").strip().lower()
        jid = str(p.get("id") or "").strip()
        with self.lock:
            if cmd == "start":
                if not jid:
                    while True:
                        self.cli_n += 1
                        jid = f"cli-{self.cli_n}"
                        if jid not in self.jobs:
                            break
                if jid in self.jobs:
                    return {"ok": False, "error": f"job {jid} already exists"}
                job = self._new_job(jid, str(p.get("title") or "Test task"),
                                    str(p.get("project") or "cmd"), kind="cli")
                self._bump()
                who = ROSTER[job["worker"]]["name"] if job["worker"] is not None else None
                return {"ok": True, "id": jid, "worker": who, "station": job["station"]}
            if cmd == "list":
                return {"ok": True, "jobs": self._public_jobs()}
            if cmd == "clear" or (cmd == "done" and jid == "all"):
                for k in list(self.jobs):
                    self._finish(k, "sent everyone home")
                self.closed.clear()
                self._bump()
                return {"ok": True}
            job = self._resolve(jid)
            if not job:
                return {"ok": False, "error": "no such job" if jid else "no jobs running"}
            msg = p.get("message")
            if cmd in ("working", "work", "resume"):
                self._set_status(job, "working", str(msg or ""))
            elif cmd == "trouble":
                self._set_status(job, "trouble", str(msg or "Something broke"))
            elif cmd in ("wait", "waiting"):
                self._set_status(job, "waiting", str(msg or "Waiting on you"))
            elif cmd == "done":
                self._finish(job["id"], "marked done")
            elif cmd != "activity":
                return {"ok": False, "error": f"unknown command {cmd!r}"}
            if p.get("activity") is not None and job["id"] in self.jobs:
                job["activity"] = clip(p.get("activity"), 60)
            self._bump()
            return {"ok": True, "id": job["id"]}

    # ---- state for the page -----------------------------------------------------------
    def _public_jobs(self) -> list[dict]:
        return [{k: j[k] for k in PUBLIC_JOB_KEYS}
                for j in sorted(self.jobs.values(), key=lambda j: j["seq"])]

    def snapshot(self, since: int = 0, wait: float = 0) -> dict:
        with self.lock:
            deadline = time.time() + wait
            while self.rev == since and time.time() < deadline:
                self.lock.wait(max(0.0, deadline - time.time()))
            return {"rev": self.rev, "now": time.time(), "roster": ROSTER, "stations": STATIONS,
                    "jobs": self._public_jobs(), "recent": self.recent}

    def reap(self) -> None:
        """Send home jobs that have gone silent (e.g. a session that crashed)."""
        cutoff = time.time() - EXPIRE_HOURS * 3600
        with self.lock:
            stale = [k for k, j in self.jobs.items() if j["updated"] < cutoff]
            for k in stale:
                self._finish(k, f"no news for {EXPIRE_HOURS} hours")
            if stale:
                self._bump()


OFFICE = Office()


class Viewers:
    """Counts open pages (each keeps a long-poll running) so the standalone app can quit
    once its window has been closed for a while."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.last_seen = time.time()

    def enter(self) -> None:
        with self.lock:
            self.active += 1
            self.last_seen = time.time()

    def leave(self) -> None:
        with self.lock:
            self.active -= 1
            self.last_seen = time.time()

    def idle_for(self) -> float:
        with self.lock:
            return 0.0 if self.active else time.time() - self.last_seen


VIEWERS = Viewers()


class Handler(BaseHTTPRequestHandler):
    server_version = "ClaudeOffice/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def _send(self, code: int, body: object, ctype: str = "application/json; charset=utf-8") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(RESOURCES, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif u.path == "/api/state":
            q = parse_qs(u.query)
            try:
                since = int((q.get("since") or ["0"])[0] or 0)
            except ValueError:
                since = 0
            VIEWERS.enter()
            try:
                self._send(200, OFFICE.snapshot(since, LONG_POLL_SECONDS if since else 0))
            finally:
                VIEWERS.leave()
        elif u.path == "/api/ping":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        # JSON only: a cross-site form post can't send this type without a CORS preflight,
        # which we never answer, so other web pages can't drive the office.
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self._send(415, {"ok": False, "error": "send application/json"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            self._send(413, {"ok": False, "error": "too big"})
            return
        try:
            p = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        if not isinstance(p, dict):
            self._send(400, {"ok": False, "error": "send an object"})
            return
        path = urlparse(self.path).path
        if path == "/api/hook":
            OFFICE.handle_hook(p)
            self._send(200, {"ok": True})
        elif path == "/api/cmd":
            self._send(200, OFFICE.handle_cmd(p))
        else:
            self._send(404, {"ok": False, "error": "not found"})


def _reaper() -> None:
    while True:
        time.sleep(60)
        OFFICE.reap()


def default_port() -> int:
    return int(os.environ.get("CLAUDE_OFFICE_PORT") or DEFAULT_PORT)


def state_file(port: int) -> str:
    """Where the office remembers its jobs: %LOCALAPPDATA%/ClaudeOffice/state.json, one per port
    (state-8790.json on port 8790), so a test office never touches the real one."""
    base = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ClaudeOffice")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "state.json" if port == DEFAULT_PORT else f"state-{port}.json")


def make_server(port: int) -> ThreadingHTTPServer:
    """Bind the office on 127.0.0.1:port, reload its saved jobs and start the stale-job reaper
    (raises OSError if the port is taken)."""
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    OFFICE.load(state_file(port))
    OFFICE.reap()
    httpd.daemon_threads = True
    threading.Thread(target=_reaper, daemon=True).start()
    return httpd


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else default_port()
    httpd = make_server(port)
    print(f"Claude Office is open at http://127.0.0.1:{port}/  (Ctrl+C to close)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
