"""Claude Office Workers: a tiny local server that turns Claude Code activity into an
animated office.

Run:   py src/server.py [port]   (or scripts/start.bat)          (default 8777, or env CLAUDE_OFFICE_PORT)
Open:  http://127.0.0.1:8777/

Claude Code reports in through claude_hook.py (wired up by install_hooks.py), which
POSTs each hook payload to /api/hook. office.py sends manual commands to /api/cmd.
The page long-polls /api/state and does all the animation itself; on closing it posts /api/bye.
Opening the office reads every transcript changed today, and each hook lets it read what's new in
that session's transcript, for today's token usage and cost (see Usage).

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
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
RESOURCES = getattr(sys, "_MEIPASS", HERE)   # where index.html lives (bundled in the exe)
DEFAULT_PORT = 8777
CURSOR_PORT = 8778     # the Cursor office: a second process of this same program (--cursor)
PRODUCT = "Claude"     # which tool this process's office watches; the page shows it in its labels
CURSOR_USAGE_URL = "https://api.cursor.com/teams/filtered-usage-events"
CURSOR_SUMMARY_URL = "https://cursor.com/api/usage-summary"     # these two take your Cursor login; undocumented
CURSOR_PERIOD_URL = "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage"
CURSOR_COST_SECONDS = 3600   # Cursor aggregates this data hourly and asks for at most one poll an hour
CURSOR_COST_LOGIN_SECONDS = 900
CURSOR_COST_MAX_PAGES = 50
EXPIRE_HOURS = 12      # a job with no news for this long is sent home
RECENT_MAX = 12        # finished jobs kept for the "Recently finished" list
AFFINITY_MAX = 300     # sessions whose worker we remember
HELPER_QUIET_MINUTES = 10   # a helper silent this long no longer keeps its lead from waiting on you
LINKS_MAX = 500        # subagents whose character we remember (dropped when their session ends)
PENDING_SECONDS = 600  # a lead's Agent call no subagent started from within this long is dropped
AGENT_NAME_RE = re.compile(r"^([A-Z][\w-]{1,20})\s*[:—–-]\s")   # "Neo: fix three bugs" -> Neo
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
                   "worker", "station", "created", "updated", "prompt", "area", "agent", "agent_type",
                   "waited", "wait_since")

# Work areas: what kind of work a job is doing, guessed from the prompt, the project folder
# and the tools Claude uses. Only job info now: stations go by who is free, not by kind of work
# (see _pick_station), so workers spread around the office and rotate with each new task.
AREA_RULES = {
    "support": r"\bsupport (?:ticket|case|request)s?\b|\bincidents?\b|\boutages?\b|\bprod(?:uction)? (?:issue|is down|down)\b"
               r"|\bhot ?fix\b|\bnot working\b|\bbroken\b|\bcustomer (?:issue|complaint)\b",
    "dbproj": r"\.dacpac\b|\bdacpacs?\b|\.sqlproj\b|\bsqlpackage\b|\bpublish profile\b|\bpre-?deployment\b"
              r"|\bpost-?deployment\b|\bscripted deploy|\bdatabase projects?\b|\bdb projects?\b|\bschema compare\b",
    "sql": r"\.sql\b|\bstored proc(?:edure)?s?\b|\bsprocs?\b|\bsql server\b|\bt-?sql\b|\bsqlcmd\b|\binvoke-sqlcmd\b"
           r"|\bselect\s+[^;]{1,200}?\s+from\s|\bssms\b|\bcreate (?:table|view|procedure|function)\b",
    "azure": r"portal\.azure\.com|\bazure portal\b|\baz (?:sql|webapp|functionapp|keyvault|group|resource|storage|vm|login|account)\b"
             r"|\bresource groups?\b|\bkey ?vaults?\b|\bapp services?\b|\bazure sql\b|\bfunction apps?\b|\bazure (?:database|storage|subscription)",
    "ado": r"dev\.azure\.com|visualstudio\.com|\bazure devops\b|\bado\b|\bab#\d+|\bwork ?items?\b|\buser stor(?:y|ies)\b"
           r"|\bpbis?\b|\baz (?:devops|boards|repos|pipelines)\b|\bsprint\b|\bbacklog\b",
    "github": r"github\.com|\bgithub\b|\bgh (?:pr|repo|issue|run|api)\b|\bpull requests?\b|\bgit (?:push|pull|merge|rebase|branch|commit|clone|fetch|cherry-pick)\b"
              r"|\bgit checkout -b\b|\bbranch(?:es)?\b|\bmerge conflicts?\b",
    "impl": r"\bgo-?lives?\b|\brollouts?\b|\bonboarding\b|\bfeature (?:flags?|toggles?)\b|\benv(?:ironment)? var(?:iable)?s?\b"
            r"|appsettings|\bweb\.config\b|\bapp\.config\b|(?:^|[\s/\\])\.env\b|\bconfig(?:uration)? (?:change|update|file)s?\b"
            r"|\b(?:client|tenant|customer) (?:config|setup)\b",
    "python": r"\.py\b|\bpython\b|\bpip install\b|\bpy (?:-m|[\w./\\-]+\.py)\b|\bdjango\b|\bflask\b|\bpandas\b|\bpyinstaller\b",
    "service": r"\bservice code\b|\bwindows services?\b|\bworker services?\b|\bhosted services?\b|\.services?\b|\bservices?\.cs\b|\blegacy\b",
    "qa": r"\bunit tests?\b|\bintegration tests?\b|\bnpm (?:run )?test\b|\bdotnet test\b|\bpytest\b|\bplaywright\b|\bselenium\b"
          r"|\bregression tests?\b|\bqa\b|\btest (?:plan|case)s?\b",
    "hardware": r"\bprinters?\b|\bdrivers?\b|\bbios\b|\bfirmware\b|\bgpu\b|\bdisk space\b|\bssd\b|\busb\b|\bdocking station\b"
                r"|\bhardware\b|\bbluetooth\b|\bwebcam\b",
    "tracking": r"\btracking (?:number|info|board|sheet)s?\b|\bshipments?\b|\btime ?sheets?\b|\btaskmaskitator\b|\btime ?tracking\b"
                r"|\bstatus reports?\b|\bdaily reports?\b|\btrack (?:time|hours|shipments?|packages?)\b",
}
AREA_RES = {k: re.compile(v, re.I) for k, v in AREA_RULES.items()}
AREA_MIN_SECONDS = 20      # the guessed area holds this long before tool calls change it
AREA_TEXT_MAX = 6000


def classify(text: str) -> list[str]:
    """Work areas whose keywords appear in text."""
    text = str(text or "")[:AREA_TEXT_MAX]
    return [k for k, rx in AREA_RES.items() if rx.search(text)]


def tool_text(name: str, inp: object) -> str:
    """Tool name (split into words, so mcp__azure-devops__wit_get_work_item reads as
    'azure devops ... work item') plus the tool input values the hook keeps."""
    words = re.sub(r"[_\-]+", " ", name or "")
    vals = " ".join(str(v) for v in inp.values()) if isinstance(inp, dict) else ""
    return f"{words} {vals}"


PASTE_RE = re.compile(r"<pasted_content\b[^>]*>(.*?)(?:</pasted_content>|\Z)", re.S | re.I)
TAG_RE = re.compile(r"</?[A-Za-z][\w:-]*(?:\s[^<>]*)?/?>")
LINE_MARK_RE = re.compile(r"^\s*(?:#{1,6}\s*|>\s*|[-*+]\s+|\d+[.)]\s+)")


FENCE_RE = re.compile(r"^\s*(```|~~~)[^\n]*\n.*?(?:^\s*\1[^\n]*$|\Z)", re.S | re.M)
RULE_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$|^\s*([-*_])(?:\s*\1){2,}\s*$")


def plain_text(text: object) -> str:
    """Markup-free one-liner for a slip or bubble: drops tags Claude Code wraps around
    prompts (e.g. <pasted_content>) and Markdown (#, **, `, list bullets, links, code
    blocks, table separator rows and rules; table cells are joined with " · ")."""
    text = FENCE_RE.sub(" ", TAG_RE.sub(" ", str(text or "")))
    lines = []
    for line in text.splitlines():
        if RULE_RE.match(line):
            continue
        if line.strip().startswith("|"):
            lines.append(" · ".join(c.strip() for c in line.strip().strip("|").split("|") if c.strip()))
        else:
            lines.append(LINE_MARK_RE.sub("", line))
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", " ".join(lines))
    text = re.sub(r"\*\*|__|~~|`+", "", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])|(?<!\w)_(?=\S)([^_]+?)(?<=\S)_(?!\w)", lambda m: m.group(1) or m.group(2), text)
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


def agent_name(name: object, description: object) -> str:
    """A subagent's own name: the Agent tool's name, else the "Name: ..." start of its
    description; "" if it has none."""
    if isinstance(name, str) and name.strip():
        return clip(name, 24)
    m = AGENT_NAME_RE.match(str(description or ""))
    return m.group(1) if m else ""


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


# ---- Token usage and cost for today (Eastern time) -----------------------------------
# API list prices in $ per million tokens: (model id prefix, input, output, cache read), from
# https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-10-30). Cache writes cost
# 1.25x input (5-minute cache) or 2x input (1-hour cache); fast mode costs 2x everything, and
# US-only inference (inference_geo "us") 1.1x.
# The longest matching prefix wins. Update this when prices change or a new model comes out:
# a model missing here still counts its tokens, but shows no cost.
PRICES = [
    ("claude-fable-5-1", 10, 50, 0.25), ("claude-mythos-5-1", 10, 50, 0.25),
    ("claude-fable-5", 10, 50, 1.00), ("claude-mythos-5", 10, 50, 1.00),
    ("claude-opus-5-5", 4, 20, 0.20), ("claude-opus-5", 5, 25, 0.50),
    ("claude-opus-4-8", 5, 25, 0.50), ("claude-opus-4-7", 5, 25, 0.50),
    ("claude-opus-4-6", 5, 25, 0.50), ("claude-opus-4-5", 5, 25, 0.50),
    ("claude-opus-4", 15, 75, 1.50), ("claude-3-opus", 15, 75, 1.50),
    ("claude-sonnet-5-5", 2, 10, 0.10), ("claude-sonnet-5", 2, 10, 0.20),
    ("claude-sonnet-4", 3, 15, 0.30), ("claude-3-7-sonnet", 3, 15, 0.30),
    ("claude-haiku-5-5", 0.10, 0.50, 0.01), ("claude-haiku-4-5", 1, 5, 0.10),
    ("claude-3-5-haiku", 0.80, 4, 0.08),
]
# Models whose price goes up for long prompts: prefix -> (prompt tokens over which, input, output, cache read)
LONG_PRICES = {"claude-haiku-5-5": (100_000, 0.50, 2.50, 0.05)}
USAGE_FILES_MAX = 400      # transcripts whose read position we remember


def price_of(model: str) -> tuple | None:
    best = None
    for row in PRICES:
        if model.startswith(row[0]) and (best is None or len(row[0]) > len(best[0])):
            best = row
    return best


def message_cost(model: str, u: dict) -> float | None:
    """API-price cost in $ of one message's usage block, or None for a model with no price."""
    row = price_of(model)
    if not row:
        return None
    n = lambda k, d=u: int(d.get(k) or 0) if isinstance(d.get(k), (int, float)) else 0
    cin, cout, cread = row[1], row[2], row[3]
    prompt = n("input_tokens") + n("cache_creation_input_tokens") + n("cache_read_input_tokens")
    long = LONG_PRICES.get(row[0])
    if long and prompt > long[0]:
        cin, cout, cread = long[1], long[2], long[3]
    split = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else None
    w1h = n("ephemeral_1h_input_tokens", split) if split else 0
    w5m = n("cache_creation_input_tokens") - w1h
    cost = (n("input_tokens") * cin + n("output_tokens") * cout + n("cache_read_input_tokens") * cread
            + w5m * cin * 1.25 + w1h * cin * 2) / 1e6
    if u.get("speed") == "fast":
        cost *= 2
    if u.get("inference_geo") == "us":
        cost *= 1.1
    return cost


def eastern_offset(ts: float) -> int:
    """Hours from UTC to US Eastern time at ts: daylight time (-4) from 2 a.m. on the second Sunday of
    March to 2 a.m. on the first Sunday of November, else -5. Worked out here because Windows Python has
    no time zone data without an extra package."""
    utc = datetime.fromtimestamp(ts, timezone.utc)
    mar1 = datetime(utc.year, 3, 1, 7, tzinfo=timezone.utc)      # 2 a.m. EST
    nov1 = datetime(utc.year, 11, 1, 6, tzinfo=timezone.utc)     # 2 a.m. EDT
    start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)
    return -4 if start <= utc < end else -5


def eastern_day(ts: float) -> str:
    """The Eastern-time date at ts, as YYYY-MM-DD."""
    return (datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=eastern_offset(ts))).strftime("%Y-%m-%d")


class Usage:
    """Tokens and cost per model for today (Eastern time), read from Claude Code's transcripts. It writes
    each reply's model and token counts to the session's transcript; the office reads only the lines added
    since it last looked, counts each message once, and starts over at midnight Eastern or when you reset
    it. Kept in memory only: opening the office counts today again from every transcript changed today
    (scan_today), and after that from the sessions that report in. A reset lasts until the office closes."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.files: dict[str, int] = {}        # transcript path -> bytes read so far
        self.seen: set[str] = set()            # message ids counted today
        self.day = eastern_day(time.time())
        self.since = 0.0                       # when you last reset; messages before it don't count
        self.models: dict[str, dict] = {}

    def _roll(self) -> None:
        today = eastern_day(time.time())
        if today != self.day:
            self.day, self.models, self.seen = today, {}, set()

    def _add(self, rec: dict) -> bool:
        msg = rec.get("message")
        if rec.get("type") != "assistant" or not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
            return False
        model, mid = str(msg.get("model") or ""), str(msg.get("id") or rec.get("requestId") or rec.get("uuid") or "")
        if not model.startswith("claude") or not mid or mid in self.seen:   # "<synthetic>": Claude Code's own notes
            return False
        try:
            ts = datetime.fromisoformat(str(rec.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return False
        if ts < self.since or eastern_day(ts) != self.day:
            return False
        self.seen.add(mid)
        u = msg["usage"]
        n = lambda k: int(u.get(k) or 0) if isinstance(u.get(k), (int, float)) else 0
        m = self.models.setdefault(model, {"model": model, "input": 0, "cache_write": 0, "cache_read": 0,
                                           "output": 0, "cost": 0.0, "messages": 0, "priced": True})
        m["input"] += n("input_tokens")
        m["cache_write"] += n("cache_creation_input_tokens")
        m["cache_read"] += n("cache_read_input_tokens")
        m["output"] += n("output_tokens")
        m["messages"] += 1
        cost = message_cost(model, u)
        if cost is None:
            m["priced"] = False
        else:
            m["cost"] += cost
        return True

    def _read(self, path: str) -> bool:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        pos = self.files.get(path, 0)
        if size < pos:                         # rewritten: start over (counted messages are skipped by id)
            pos = 0
        if size == pos:
            return False
        with open(path, "rb") as f:
            f.seek(pos)
            data = f.read(size - pos)
        end = data.rfind(b"\n") + 1            # a half-written last line waits for the next look
        self.files.pop(path, None)
        self.files[path] = pos + end
        while len(self.files) > USAGE_FILES_MAX:
            self.files.pop(next(iter(self.files)))
        changed = False
        for line in data[:end].splitlines():
            if b'"usage"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and self._add(rec):
                changed = True
        return changed

    def scan(self, p: dict) -> bool:
        """Read what's new in the transcripts of the session a hook came from: the session's own and
        its subagents' (<session>/subagents/*.jsonl beside it). True if a count changed. A hook with
        no transcript on disk (the test buttons, office.py) counts nothing."""
        path, sid = p.get("transcript_path"), str(p.get("session_id") or "")
        if not (isinstance(path, str) and path.endswith(".jsonl") and os.path.isfile(path)):
            return False
        paths = [path]
        folder = os.path.dirname(path)
        if os.path.basename(folder) != "subagents" and sid and all(c.isalnum() or c in "-_" for c in sid):
            folder = os.path.join(folder, sid, "subagents")
        if os.path.basename(folder) == "subagents":
            try:
                paths += [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".jsonl")]
            except OSError:
                pass
        with self.lock:
            self._roll()
            changed = False
            for f in dict.fromkeys(paths):
                try:
                    changed = self._read(f) or changed
                except OSError:
                    pass
            return changed

    def scan_today(self) -> bool:
        """Read what's new in every transcript changed today, reporting in or not. True if a count changed."""
        root = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "projects")
        now = time.time()
        midnight = now - (now + eastern_offset(now) * 3600) % 86400
        changed = False
        for folder, _, names in os.walk(root):
            for name in names:
                path = os.path.join(folder, name)
                try:
                    if name.endswith(".jsonl") and os.path.getmtime(path) >= midnight:
                        with self.lock:       # file by file, so hooks and the page never wait for the whole walk
                            self._roll()
                            changed = self._read(path) or changed
                except OSError:
                    pass
        return changed

    def reset(self) -> None:
        """Start today's count over from now."""
        with self.lock:
            self.since, self.models = time.time(), {}

    def public(self) -> dict:
        with self.lock:
            self._roll()
            models = sorted((dict(m, cost=round(m["cost"], 6)) for m in self.models.values()),
                            key=lambda m: -m["cost"])
            return {"day": self.day, "since": self.since if eastern_day(self.since or 0) == self.day else 0,
                    "models": models}


USAGE = Usage()


class Office:
    """All jobs and the worker rotation. Every method takes self.lock."""

    def __init__(self) -> None:
        self.lock = threading.Condition()
        self.rev = 1
        self.jobs: dict[str, dict] = {}
        self.seq = 0
        self.used: set[int] = set()            # workers who have had a turn this rotation
        self.helpers_done: dict[str, float] = {}   # "sid:agent_id" -> when it stopped, to ignore late starts
        # each subagent's character, so it keeps it within the session (freed when the session ends):
        # "<session>:name:<name>" or "<session>:<agent id>" -> {"w": worker, "sid", "name", "desc"}
        self.links: dict[str, dict] = {}
        self.recent: list[dict] = []
        self.closed: set[str] = set()          # sessions marked done while their turn finishes
        self.cli_n = 0
        self.state_path = ""                   # set by load(); empty means don't save
        # who did each session's last task, so the same task keeps the same worker (at a new station):
        # key (session id, or "<session>:<agent type>" for helpers) -> [worker, station]
        self.affinity: dict[str, list] = {}

    # ---- internals (caller holds the lock) -------------------------------------------
    def _bump(self) -> None:
        self.rev += 1
        self.lock.notify_all()
        self._save()

    def poke(self) -> None:
        """Wake the pages for news outside the jobs (today's token usage)."""
        with self.lock:
            self.rev += 1
            self.lock.notify_all()

    # ---- saved state, so restarting the office keeps everyone where they were ----------
    def _save(self) -> None:
        if not self.state_path:
            return
        data = {"jobs": self.jobs, "seq": self.seq, "used": sorted(self.used), "recent": self.recent,
                "closed": sorted(self.closed), "cli_n": self.cli_n, "affinity": self.affinity,
                "links": self.links}
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
            for j in self.jobs.values():       # saved before the timer paused: its wait began at the last update
                if j.get("status") == "waiting" and not j.get("wait_since"):
                    j["wait_since"] = j.get("updated") or time.time()
            self.seq = int(data.get("seq") or 0)
            self.used = set(data.get("used") or [])
            self.recent = list(data.get("recent") or [])[:RECENT_MAX]
            self.closed = set(data.get("closed") or [])
            self.cli_n = int(data.get("cli_n") or 0)
            self.affinity = {k: v for k, v in (data.get("affinity") or {}).items() if isinstance(v, list) and len(v) == 2}
            self.links = {k: v for k, v in (data.get("links") or {}).items()
                          if isinstance(v, dict) and isinstance(v.get("w"), int)}

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

    def _pick_station(self, job: dict | None = None, leave: str | None = None) -> str:
        """A station nobody else holds (a random one), else the one with the fewest workers.
        leave: the station a returning session's worker had last time; they get another one unless it's the only one with room."""
        counts = {s: 0 for s in STATIONS}
        for j in self.jobs.values():
            if j is not job and j["worker"] is not None and j["station"] in counts:
                counts[j["station"]] += 1
        low = min(counts.values())
        options = [s for s, c in counts.items() if c == low and s != leave] or [leave]
        return random.choice(options)

    def _staff(self, job: dict) -> None:
        """Give the job a worker: the one who did this session's last task if they're free,
        otherwise the next in the rotation."""
        if job["worker"] is not None:
            return
        if job["kind"] == "helper":
            self._staff_helper(job)
            return
        key = job.get("key") or job["id"]
        pref = self.affinity.get(key)
        if pref and pref[0] not in self._busy() and 0 <= pref[0] < len(ROSTER):
            job["worker"], job["station"] = pref[0], self._pick_station(job, pref[1])   # same worker, next station
            self.used.add(pref[0])
        else:
            job["worker"] = self._pick_worker()
            if job["worker"] is None:
                return
            job["station"] = self._pick_station()
        self.affinity.pop(key, None)
        self.affinity[key] = [job["worker"], job["station"]]
        while len(self.affinity) > AFFINITY_MAX:
            self.affinity.pop(next(iter(self.affinity)))

    def _staff_helper(self, job: dict) -> None:
        """A subagent gets its own character for the whole session: the one linked to its key if
        free, else a random free one nobody's live session has linked, else one linked to another
        session's idle agent, else any free one (only then two agents of one session share)."""
        key, sid = job.get("key") or job["id"], job.get("sid") or ""
        busy = self._busy()
        link = self.links.get(key)
        w = link["w"] if link and 0 <= link["w"] < len(ROSTER) and link["w"] not in busy else None
        if w is None:
            free = [r["id"] for r in ROSTER if r["id"] not in busy]
            own = {l["w"] for l in self.links.values() if l.get("sid") == sid}
            other = {l["w"] for l in self.links.values() if l.get("sid") != sid and l.get("sid") in self.jobs}
            for tier in ([r for r in free if r not in own and r not in other], [r for r in free if r not in own], free):
                if tier:
                    w = random.choice(tier)
                    break
            else:
                return                         # nobody free: queued until someone goes home
        job["worker"], job["station"] = w, self._pick_station()
        self.used.add(w)
        rec = {"w": w, "sid": sid, "name": job.get("agent") or "", "desc": job.get("desc") or ""}
        for k in {key, job.get("aid_key") or key}:
            self.links.pop(k, None)
            self.links[k] = dict(rec)
        while len(self.links) > LINKS_MAX:
            self.links.pop(next(iter(self.links)))

    def _take_call(self, job: dict, tool_use_id: object, kind: str) -> dict | None:
        """The lead's Agent call that started this subagent: the one with its tool_use_id, else
        (no id known) the oldest call of its type, marked as a guess. Calls older than
        PENDING_SECONDS (denied or failed ones) are dropped."""
        pending = [c for c in job.get("pending_agents") or [] if time.time() - c.get("t", 0) < PENDING_SECONDS]
        job["pending_agents"] = pending
        if tool_use_id:
            call, guess = next((c for c in pending if c.get("id") == tool_use_id), None), False
        else:
            call, guess = next((c for c in pending if c["type"] in ("", kind)), None), True
        if call:
            pending.remove(call)
            return dict(call, guess=guess)
        return None

    def _describe_helper(self, helper: dict, desc: str) -> None:
        """The subagent's description arrived (from its meta file): it becomes the slip's title.
        A "Name: ..." in it names the agent, over any other name; without one, a name guessed
        from the lead's Agent calls is dropped and the agent goes back to its agent-id key. Its
        character stays the same either way; the new key is linked to it."""
        desc, sid, old_key = clip(desc, 120), helper.get("sid") or "", helper.get("key")
        name = agent_name(None, desc) or ("" if helper.get("agent_guess") else helper.get("agent") or "")
        if helper.get("agent_guess") and old_key != helper.get("aid_key") and name != helper.get("agent"):
            link = self.links.get(old_key)
            if link and link["w"] == helper["worker"]:
                del self.links[old_key]        # the wrong guess's link
        helper["desc"], helper["title"], helper["agent"], helper["agent_guess"] = desc, desc, name, False
        helper["key"] = f"{sid}:name:{name.lower()}" if name else helper.get("aid_key") or helper["id"]
        if helper["worker"] is not None:
            rec = {"w": helper["worker"], "sid": sid, "name": name, "desc": desc}
            for k in {helper["key"], helper.get("aid_key") or helper["key"]}:
                self.links.pop(k, None)
                self.links[k] = dict(rec)

    def _new_job(self, jid: str, title: str, project: str = "", kind: str = "main",
                 parent: str | None = None, ts: float | None = None, key: str | None = None,
                 extra: dict | None = None) -> dict:
        now = time.time()
        self.seq += 1
        job = {"id": jid, "title": clip(title, 120) or "(untitled task)", "project": clip(project, 40),
               "kind": kind, "parent": parent, "status": "working", "message": "", "activity": "",
               "prompt": "", "worker": None, "station": None, "created": now, "updated": now,
               "status_ts": ts or now, "seq": self.seq, "key": key or jid,
               "area": "", "area_ts": 0.0, "scores": {}}
        job.update(extra or {})
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
        # the card's timer stops while the job waits on you: remember when the wait began
        # and add each finished wait to "waited". Timed on the server's clock (like "created"),
        # not the hook's ts, so the page subtracts like from like.
        if status == "waiting" and not job.get("wait_since"):
            job["wait_since"] = job["updated"]
        elif status != "waiting" and job.get("wait_since"):
            job["waited"] = job.get("waited", 0.0) + job["updated"] - job["wait_since"]
            job["wait_since"] = None
        if message is not None:
            job["message"] = clip(message, 200)

    def _finish(self, jid: str, reason: str) -> None:
        """Send the job's worker home. reason shows in "Recently finished" so you can tell why."""
        job = self.jobs.pop(jid, None)
        if not job:
            return
        for child in [j for j in self.jobs.values() if j["parent"] == jid]:
            self._finish(child["id"], reason)
        if job["kind"] != "helper":            # the session is over: free its subagents' characters
            for k in [k for k, l in self.links.items() if l.get("sid") == jid]:
                del self.links[k]
            for k in [k for k in self.affinity if k.startswith(jid + ":")]:
                del self.affinity[k]
        self.recent.insert(0, {"id": job["id"], "title": job["title"], "project": job["project"],
                               "worker": job["worker"], "created": job["created"],
                               "finished": time.time(), "reason": reason})
        del self.recent[RECENT_MAX:]
        for queued in sorted(self.jobs.values(), key=lambda j: j["seq"]):
            if queued["worker"] is None:
                self._staff(queued)
                if queued["worker"] is None:
                    break

    def _signal(self, job: dict, text: str, weight: float, fresh: bool = False) -> None:
        """Score the work areas named in text and set the job's area to the leader. A new prompt
        (fresh) is a new focus: old scores mostly fade and the area may change at once; tool
        calls only move it once the new area clearly leads and the area has held a while."""
        hits = classify(text)
        scores = job.setdefault("scores", {})
        if not hits and not fresh:
            return
        for k in list(scores):
            scores[k] = round(scores[k] * (0.3 if fresh else 0.85), 3)
        for a in hits:
            scores[a] = scores.get(a, 0) + weight
        if not scores:
            return
        best = max(scores, key=scores.get)
        cur = job.get("area") or ""
        if best == cur or scores[best] < 2:
            return
        if cur and not fresh and (time.time() - job.get("area_ts", 0) < AREA_MIN_SECONDS
                                  or scores[best] < scores.get(cur, 0) * 1.5 + 1):
            return
        job["area"] = best
        job["area_ts"] = time.time()

    def _resolve(self, jid: str) -> dict | None:
        if jid and jid != "last":
            return self.jobs.get(jid)
        return max(self.jobs.values(), key=lambda j: j["seq"], default=None)

    def _helpers(self, sid: str, fresh: bool = True) -> list[dict]:
        """The session's helpers; fresh: only those heard from lately (a lost SubagentStop
        must not keep the lead from ever waiting on you)."""
        cutoff = time.time() - HELPER_QUIET_MINUTES * 60 if fresh else 0
        return [j for j in self.jobs.values() if j["parent"] == sid and j["updated"] >= cutoff]

    def _helper_wait(self, sid: str) -> str:
        n = len(self._helpers(sid))
        return f"Waiting for {n} helper{'s' if n != 1 else ''}"

    def _release_lead(self, job: dict) -> bool:
        """A lead whose turn ended (Stop) while helpers were out: once none is left, it waits
        on you with what it said when it stopped. Returns True if anything changed."""
        if job.get("stop_ts") != job["status_ts"] or job["status"] == "trouble":
            return False
        if self._helpers(job["id"]):
            if job["status"] != "working" or job["activity"] == self._helper_wait(job["id"]):
                return False
            job["activity"] = self._helper_wait(job["id"])
        elif job["status"] == "working" or job["message"] != job.get("stop_msg"):
            job["status"], job["message"], job["activity"] = "waiting", job.get("stop_msg") or "", ""
        else:
            return False
        return True

    def _name_session(self, sid: str, name: str) -> None:
        """Use the session's name from the Claude app (a rename, or its auto title) as the
        job title, and as the helpers' "... helper for: <name>"."""
        job = self.jobs.get(sid)
        if not job:
            return
        job["title"] = name
        for h in self._helpers(sid, fresh=False):
            if h.get("desc"):
                continue                       # titled with its own description
            h["title"] = clip(f"{h.get('agent_type') or 'helper'} helper for: {name}", 120)

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
            desc = clip(plain_text(p.get("agent_description")), 120) if agent_id else ""
            if desc and f"{sid}:{agent_id}" in self.jobs:
                self._describe_helper(self.jobs[f"{sid}:{agent_id}"], desc)
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
                    job["pending_agents"] = []         # Agent calls from an earlier turn that never started
                    job["activity"] = "Reading your message"
                    self._set_status(job, "working", "", ts)
                    self._signal(job, plain_text(p.get("prompt")), 4, fresh=True)
                    self._signal(job, cwd, 2)
            elif ev == "PreToolUse":
                if sid in self.closed:
                    return
                target = self.jobs.get(f"{sid}:{agent_id}") if agent_id else None
                if target is None:
                    if not job:
                        job = self._new_job(sid, "(picking up where we left off)", project, ts=ts)
                    target = job
                ti = p.get("tool_input") if isinstance(p.get("tool_input"), dict) else {}
                if not agent_id and p.get("tool_name") in ("Agent", "Task"):   # the lead's own call: who the next helper is
                    job.setdefault("pending_agents", []).append(
                        {"name": agent_name(ti.get("name"), ti.get("description")),
                         "desc": clip(ti.get("description"), 120), "type": str(ti.get("subagent_type") or ""),
                         "id": str(p.get("tool_use_id") or ""), "t": time.time()})
                    del job["pending_agents"][:-10]
                target["activity"] = describe_tool(str(p.get("tool_name") or ""), p.get("tool_input"))
                self._set_status(target, "working", "", ts)
                if not target.get("area"):
                    self._signal(target, cwd, 2)
                self._signal(target, tool_text(str(p.get("tool_name") or ""), p.get("tool_input")), 1)
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
                msg = plain_text(p.get("message"))
                ntype = str(p.get("notification_type") or "")
                idle = ntype == "idle_prompt" or (not ntype and "waiting for your input" in msg.lower())
                if idle and self._helpers(sid):
                    return  # the lead is waiting on its helpers, not on you
                armed = job.get("stop_ts") == job["status_ts"]
                self._set_status(job, "waiting", msg or "Waiting on you", ts)
                if armed and job["status_ts"] == ts:
                    job["stop_ts"] = ts        # its turn is still over: the last SubagentStop can switch it
            elif ev == "Stop":
                if not job or sid in self.closed:
                    return
                last = clip(plain_text(p.get("last_assistant_message")), 140) or "Finished — your turn!"
                out = self._helpers(sid)       # helpers still out: it waits for them in the meeting, not on you
                self._set_status(job, "working" if out else "waiting", "" if out else last, ts)
                if job["status_ts"] == ts:     # its turn is over: the last SubagentStop (or a late
                    job["activity"] = self._helper_wait(sid) if out else ""   # SubagentStart) can switch it
                    job["stop_ts"], job["stop_msg"] = ts, last
            elif ev == "SubagentStart":
                hk = f"{sid}:{agent_id}"
                if not agent_id or sid in self.closed or ts < self.helpers_done.get(hk, 0):
                    return                     # a start that lands after its own stop is ignored
                kind = str(p.get("agent_type") or "helper")
                # who it is: a continued agent (SendMessage) keeps its name; a new one is the lead's
                # Agent call with its tool_use_id (or, with no id yet, a guess: the oldest call of its
                # type); its meta file's description, once there, wins (see _describe_helper)
                link = self.links.get(hk) or {}
                name, about, guess = link.get("name") or "", link.get("desc") or "", False
                call = self._take_call(job, p.get("agent_tool_use_id"), kind) if job and not link else None
                if call:
                    name, about, guess = call["name"], call["desc"], call["guess"]
                if desc:
                    name, about, guess = agent_name(None, desc) or ("" if guess else name), desc, False
                parent_title = job["title"] if job else ""
                title = about or f"{kind} helper" + (f" for: {parent_title}" if parent_title else "")
                if hk not in self.jobs:
                    helper = self._new_job(hk, title, project, kind="helper", parent=sid if job else None,
                                           ts=ts, key=f"{sid}:name:{name.lower()}" if name else hk,
                                           extra={"agent_type": kind, "agent": name, "desc": about,
                                                  "agent_guess": guess, "sid": sid, "aid_key": hk})
                    if job and job.get("area"):        # helpers start on their lead's kind of work
                        helper["area"], helper["area_ts"] = job["area"], 0.0
                # Async hooks can land out of order: a Stop that beat this start sent the lead to
                # the mailroom, but it is really waiting on this helper.
                if (job and job["status"] == "waiting" and job.get("stop_ts") == job["status_ts"]
                        and job["message"] == job.get("stop_msg")):
                    job["status"], job["message"] = "working", ""
                    job["activity"] = self._helper_wait(sid)
            elif ev == "SubagentStop":
                if not agent_id:
                    return
                self.helpers_done.pop(f"{sid}:{agent_id}", None)
                self.helpers_done[f"{sid}:{agent_id}"] = ts
                while len(self.helpers_done) > 200:
                    self.helpers_done.pop(next(iter(self.helpers_done)))
                self._finish(f"{sid}:{agent_id}", "helper finished")
                if job:
                    self._release_lead(job)
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
            name = clip(plain_text(p.get("session_title")), 120) if not agent_id else ""
            if name:
                self._name_session(sid, name)
            self._bump()

    # ---- manual commands (office.py / the page) ---------------------------------------
    def handle_cmd(self, p: dict) -> dict:
        cmd = str(p.get("cmd") or "").strip().lower()
        jid = str(p.get("id") or "").strip()
        if cmd == "cursor-cost":
            if PRODUCT != "Cursor":
                return {"ok": False, "error": "only the Cursor office has this"}
            CURSOR_COST.set_login(p.get("on") is True)
            self.poke()
            return {"ok": True}
        if cmd in ("usage", "usage-reset"):
            if cmd == "usage-reset":
                USAGE.reset()
                self.poke()
            return {"ok": True, "usage": USAGE.public()}
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
                if p.get("area") in AREA_RULES:
                    job["area"] = p["area"]
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
            if p.get("area") in AREA_RULES and job["id"] in self.jobs:
                job["area"], job["area_ts"] = p["area"], time.time()
            self._bump()
            return {"ok": True, "id": job["id"]}

    # ---- state for the page -----------------------------------------------------------
    def _public_jobs(self) -> list[dict]:
        return [{k: j.get(k) for k in PUBLIC_JOB_KEYS}
                for j in sorted(self.jobs.values(), key=lambda j: j["seq"])]

    def snapshot(self, since: int = 0, wait: float = 0) -> dict:
        with self.lock:
            deadline = time.time() + wait
            while self.rev == since and time.time() < deadline:
                self.lock.wait(max(0.0, deadline - time.time()))
            return {"rev": self.rev, "now": time.time(), "product": PRODUCT, "roster": ROSTER, "stations": STATIONS,
                    "jobs": self._public_jobs(), "recent": self.recent, "usage": USAGE.public(),
                    "cost": CURSOR_COST.public()}

    def reap(self) -> None:
        """Send home jobs that have gone silent (e.g. a session that crashed)."""
        cutoff = time.time() - EXPIRE_HOURS * 3600
        with self.lock:
            stale = [k for k, j in self.jobs.items() if j["updated"] < cutoff]
            for k in stale:
                self._finish(k, f"no news for {EXPIRE_HOURS} hours")
            # leads waiting on helpers that went quiet (their SubagentStop never came)
            released = [j for j in list(self.jobs.values()) if j["kind"] != "helper" and self._release_lead(j)]
            if stale or released:
                self._bump()


OFFICE = Office()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect with your login: urllib would send its headers on to the new host."""

    def redirect_request(self, *a, **k):
        return None


def cursor_state_db() -> str:
    """Where the Cursor app keeps its settings, including your login."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Cursor", "User", "globalStorage", "state.vscdb")


def read_cursor_login() -> tuple[str, str]:
    """(token, user id) from the Cursor app's own store, opened read-only so it can't change anything
    or get in Cursor's way. Raises LookupError if you aren't logged in. Not part of any documented API."""
    import base64
    import sqlite3
    from urllib.parse import quote
    path = cursor_state_db()
    if not os.path.isfile(path):
        raise LookupError("Cursor's login wasn't found on this PC")
    db = sqlite3.connect(f"file:{quote(path.replace(chr(92), '/'))}?mode=ro", uri=True, timeout=2)
    try:
        row = db.execute("SELECT value FROM ItemTable WHERE key = 'cursorAuth/accessToken' LIMIT 1").fetchone()
    finally:
        db.close()
    token = str(row[0] if row and row[0] else "").strip().strip('"')
    if not token:
        raise LookupError("Cursor isn't logged in")
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return token, str(claims["sub"]).split("|")[-1]
    except (IndexError, KeyError, ValueError, TypeError):
        raise LookupError("Cursor's login isn't in the expected format") from None


def _login_request(url: str, headers: dict, body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "Mozilla/5.0", **headers})
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_login_usage(token: str, user_id: str) -> tuple[dict, dict]:
    """The two private calls the Cursor app and dashboard use: (usage summary, current period).
    Either can come back {} with its failure in the "_error" field; the token is never in an error."""
    def attempt(url: str, headers: dict, body: bytes | None) -> dict:
        try:
            out = _login_request(url, headers, body)
            return out if isinstance(out, dict) else {"_error": "unexpected answer"}
        except urllib.error.HTTPError as e:
            return {"_error": f"HTTP {e.code}", "_status": e.code}
        except (OSError, ValueError) as e:
            return {"_error": type(e).__name__}
    return (attempt(CURSOR_SUMMARY_URL, {"Cookie": f"WorkosCursorSessionToken={user_id}%3A%3A{token}"}, None),
            attempt(CURSOR_PERIOD_URL, {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                        "Connect-Protocol-Version": "1"}, b"{}"))


def _number(v: object) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def cycle_spend(summary: dict, period: dict) -> dict | None:
    """Your own spend this billing cycle, in cents, as the Cursor settings page shows it: enterprise
    accounts report it under individualUsage.overall, others under plan plus on-demand. The team's
    pooled numbers are never used. None if neither answer has it."""
    usage = summary.get("individualUsage") if isinstance(summary.get("individualUsage"), dict) else {}
    overall, plan, extra = (usage.get(k) if isinstance(usage.get(k), dict) else {} for k in ("overall", "plan", "onDemand"))
    used, limit = _number(overall.get("used")), _number(overall.get("limit"))
    if used is None and _number(plan.get("used")) is not None:
        used, limit = _number(plan["used"]) + (_number(extra.get("used")) or 0), _number(plan.get("limit"))
    if used is None:
        pu = period.get("planUsage") if isinstance(period.get("planUsage"), dict) else {}
        used, limit = _number(pu.get("totalSpend")), _number(pu.get("limit"))
    if used is None:
        return None
    return {"cents": used, "limit": limit or 0, "resets": str(summary.get("billingCycleEnd") or "")}


def cursor_cost_report() -> str:
    """What the login route finds on this PC, safe to share: your own amounts and field names, never
    the token, your email, any id or the team's spend. For --cursor-cost-check, since Cursor's private
    answers can change."""
    lines = []
    try:
        token, user_id = read_cursor_login()
        lines.append("Login: found in Cursor's store")
    except (LookupError, OSError, ImportError) as e:
        return f"Login: {e}"
    except Exception as e:
        return f"Login: couldn't read Cursor's store ({type(e).__name__})"
    summary, period = fetch_login_usage(token, user_id)

    def private(key: str) -> bool:
        k = key.lower()     # "id" only as a whole end of the name: "individualUsage" is the part worth seeing
        return any(w in k for w in ("email", "name", "token", "team", "pool")) or k.endswith(("id", "ids"))

    def shape(v: object, depth: int = 0) -> object:
        if isinstance(v, dict) and depth < 4:
            return {k: shape(x, depth + 1) for k, x in v.items() if not private(k)}
        return v if isinstance(v, (int, float, bool)) or v is None else "(text)"
    lines.append("Usage summary: " + (summary.get("_error") or json.dumps(shape(summary))))
    lines.append("Current period: " + (period.get("_error") or json.dumps(shape(period))))
    spend = cycle_spend(summary, period)
    lines.append(f"The office would show: ${spend['cents'] / 100:.2f} of ${spend['limit'] / 100:.2f}" if spend else "The office would show: nothing, no spend found")
    return "\n".join(lines)


class CursorCost:
    """Your Cursor cost, for the Cursor office only; Cursor's hooks report none. Off by default,
    with no internet at all. Two ways on:
    - Settings checkbox (saved in cursor-cost.json): this billing cycle's spend through your Cursor
      login, read fresh from the Cursor app for each check and never saved or logged. These are
      Cursor's private calls, so they can change without notice.
    - CURSOR_ADMIN_KEY: today's cost from the documented Team Admin API, which wins if both are set.
      It returns the whole team's events without an email filter, so it never asks until it knows
      yours: CURSOR_COST_EMAIL, else the user_email a hook reports."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.key = ""
        self.login = False
        self.email = ""
        self.day = ""
        self.cents = 0.0
        self.limit = 0.0
        self.resets = ""
        self.checked = 0.0
        self.error = ""

    def _settings(self) -> str:
        return os.path.join(data_dir(), "cursor-cost.json")

    def start(self) -> None:
        self.key = os.environ.get("CURSOR_ADMIN_KEY", "").strip()
        self.email = os.environ.get("CURSOR_COST_EMAIL", "").strip()
        try:
            with open(self._settings(), encoding="utf-8") as f:
                self.login = json.load(f).get("login") is True
        except (OSError, ValueError, AttributeError):
            pass
        threading.Thread(target=self._loop, daemon=True).start()

    def set_login(self, on: bool) -> None:
        """The Settings checkbox. Remembered, so it's on again whenever the office starts."""
        with self.lock:
            self.login = on
            self.cents, self.limit, self.resets, self.checked, self.error = 0.0, 0.0, "", 0.0, ""
        os.makedirs(data_dir(), exist_ok=True)
        with open(self._settings(), "w", encoding="utf-8") as f:
            json.dump({"login": on}, f)
        self.wake.set()

    def saw_hook(self, p: dict) -> None:
        """The first hook that names you starts the first Team API check."""
        email = p.get("user_email")
        if self.key and not self.email and isinstance(email, str) and email.strip():
            self.email = email.strip()
            self.wake.set()

    def _loop(self) -> None:
        while True:
            if self.key:
                if self.email:
                    self.check()
                    OFFICE.poke()
            elif self.login:
                self.check_login()
                OFFICE.poke()
            self.wake.wait(CURSOR_COST_SECONDS if self.key else CURSOR_COST_LOGIN_SECONDS)
            self.wake.clear()

    def check_login(self) -> None:
        """This cycle's spend through your Cursor login. On a failure the last good number stays."""
        spend, error = None, ""
        try:
            token, user_id = read_cursor_login()
            summary, period = fetch_login_usage(token, user_id)
            spend = cycle_spend(summary, period)
            if not spend:
                refused = {summary.get("_status"), period.get("_status")} & {401, 403}
                error = "Cursor refused your login (open Cursor and check you're signed in)" if refused else "Cursor's answer had no spend in it"
        except LookupError as e:
            error = str(e)
        except Exception as e:     # a locked or changed database, say: never the office's problem
            error = f"Couldn't read Cursor's login ({type(e).__name__})"
        with self.lock:
            self.error = error
            if spend:
                self.cents, self.limit, self.resets, self.checked = spend["cents"], spend["limit"], spend["resets"], time.time()

    def _page(self, start_ms: int, end_ms: int, page: int) -> dict:
        import base64
        body ={"startDate": start_ms, "endDate": end_ms, "email": self.email, "page": page, "pageSize": 1000}
        auth = base64.b64encode(f"{self.key}:".encode("utf-8")).decode("ascii")
        req = urllib.request.Request(CURSOR_USAGE_URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def check(self) -> None:
        """Add up chargedCents (Cursor's documented way to get cost) over today's events. On a
        failure the last good number stays, with the reason beside it."""
        now = time.time()
        start = now - (now + eastern_offset(now) * 3600) % 86400
        cents, page, error = 0.0, 1, ""
        try:
            while True:
                data = self._page(int(start * 1000), int(now * 1000), page)
                cents += sum(float(e.get("chargedCents") or 0) for e in data.get("usageEvents") or [])
                if not (data.get("pagination") or {}).get("hasNextPage") or page >= CURSOR_COST_MAX_PAGES:
                    break
                page += 1
        except urllib.error.HTTPError as e:
            error = "Cursor refused the key (it needs a Team API key)" if e.code in (401, 403) else f"Cursor answered {e.code}"
        except (OSError, ValueError, TypeError, AttributeError) as e:
            error = f"Couldn't reach Cursor ({type(e).__name__})"
        with self.lock:
            self.error = error
            if not error:
                self.day, self.cents, self.checked = eastern_day(now), cents, now

    def public(self) -> dict | None:
        if not self.key and not self.login:
            return None
        with self.lock:
            if not self.key:
                return {"mode": "login", "cents": round(self.cents, 2), "limit": self.limit, "resets": self.resets,
                        "checked": self.checked, "error": self.error, "email": True}
            today = self.day == eastern_day(time.time())
            return {"mode": "key", "cents": round(self.cents, 2) if today else 0, "checked": self.checked if today else 0,
                    "error": self.error, "email": bool(self.email)}


CURSOR_COST = CursorCost()


class Viewers:
    """Counts open pages (each keeps a long-poll running) and their goodbyes (/api/bye on
    pagehide) so the standalone app can quit once its window has really been closed."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.last_seen = time.time()
        self.bye_at = 0.0       # when a page last said goodbye; 0 = no goodbye since the last poll
        self.seen = False       # has any page ever polled?

    def enter(self) -> None:
        with self.lock:
            self.active += 1
            self.last_seen = time.time()
            self.bye_at = 0.0   # a page is still (or again) open: cancel any goodbye
            self.seen = True

    def ever_seen(self) -> bool:
        with self.lock:
            return self.seen

    def bye(self) -> None:
        with self.lock:
            self.bye_at = time.time()

    def gone_for(self) -> float:
        """Seconds since a page said goodbye with no page polling since; 0 otherwise."""
        with self.lock:
            if not self.bye_at or self.active:
                return 0.0
            return time.time() - max(self.bye_at, self.last_seen)

    def leave(self) -> None:
        with self.lock:
            self.active -= 1
            self.last_seen = time.time()


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
        except ConnectionError:     # the page went away (closed window, aborted long-poll)
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
        if urlparse(self.path).path == "/api/bye":
            # The page's sendBeacon on pagehide: no body, no JSON. Any site could post this, but
            # all it does is let an app-mode server quit when no page is polling it, and a real
            # page's next poll cancels it, so that's harmless.
            VIEWERS.bye()
            self._send(200, {"ok": True})
            return
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
            CURSOR_COST.saw_hook(p)
            self._send(200, {"ok": True})
            if USAGE.scan(p):                  # after answering: a long transcript's first read can take a moment
                OFFICE.poke()
        elif path == "/api/cmd":
            self._send(200, OFFICE.handle_cmd(p))
        else:
            self._send(404, {"ok": False, "error": "not found"})


def _reaper() -> None:
    while True:
        time.sleep(60)
        OFFICE.reap()


def use_cursor() -> None:
    """Make this process the Cursor office: its own port (so its own state file) and name."""
    global PRODUCT
    PRODUCT = "Cursor"


def default_port() -> int:
    if PRODUCT == "Cursor":
        return int(os.environ.get("CURSOR_OFFICE_PORT") or CURSOR_PORT)
    return int(os.environ.get("CLAUDE_OFFICE_PORT") or DEFAULT_PORT)


def data_dir() -> str:
    """Where the office keeps its own files: %LOCALAPPDATA%\\ClaudeOffice on Windows,
    ~/Library/Application Support/ClaudeOffice on a Mac."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/ClaudeOffice")
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ClaudeOffice")


def state_file(port: int) -> str:
    """Where the office remembers its jobs: state.json in data_dir(), one per port
    (state-8790.json on port 8790), so a test office never touches the real one."""
    base = data_dir()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "state.json" if port == DEFAULT_PORT else f"state-{port}.json")


def _load_todays_usage() -> None:
    """The token meter on opening the office: in the background, since a long transcript's first read takes a moment."""
    try:
        if USAGE.scan_today():
            OFFICE.poke()
    except Exception:      # a transcript in a shape we don't expect: never the office's problem
        pass


def make_server(port: int) -> ThreadingHTTPServer:
    """Bind the office on 127.0.0.1:port, reload its saved jobs and start the stale-job reaper
    (raises OSError if the port is taken)."""
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    OFFICE.load(state_file(port))
    OFFICE.reap()
    httpd.daemon_threads = True
    threading.Thread(target=_reaper, daemon=True).start()
    if PRODUCT == "Cursor":
        CURSOR_COST.start()
    else:
        threading.Thread(target=_load_todays_usage, daemon=True).start()
    return httpd


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--cursor" in argv:
        argv.remove("--cursor")
        use_cursor()
    port = int(argv[0]) if argv else default_port()
    httpd = make_server(port)
    print(f"{PRODUCT} Office is open at http://127.0.0.1:{port}/  (Ctrl+C to close)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
