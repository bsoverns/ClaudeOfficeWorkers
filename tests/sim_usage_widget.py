"""Known-answer checks for src/usage_widget.py on made-up transcripts in a temp folder. Opens no window and
uses no internet. Run it after changing the widget, or the Usage or CursorCost code it relies on in server.py."""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
tmp = tempfile.mkdtemp()
os.environ["CLAUDE_CONFIG_DIR"] = tmp
import usage_widget as w

proj = os.path.join(tmp, "projects", "repo")
sub = os.path.join(proj, "sess", "subagents")
os.makedirs(sub)
now = datetime.now(timezone.utc)
stamp = now.isoformat().replace("+00:00", "Z")
old = (now - timedelta(days=3)).isoformat().replace("+00:00", "Z")


def rec(mid, model="claude-opus-5-5", ts=stamp, inp=1000, out=500, cr=0, cw=0):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {"id": mid, "model": model, "usage": {
        "input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}}})


with open(os.path.join(proj, "sess.jsonl"), "w") as f:
    f.write(rec("a") + "\n" + rec("a") + "\n")                     # same message twice counts once
    f.write(rec("yesterday", ts=old) + "\n")                       # not today
    f.write(rec("synthetic", model="<synthetic>") + "\n")          # Claude Code's own notes
    f.write("not json \"usage\"\n")
with open(os.path.join(sub, "agent.jsonl"), "w") as f:
    f.write(rec("a") + "\n" + rec("b", model="claude-sonnet-5-5", inp=2000, out=1000, cr=1000, cw=1000) + "\n")
stale = os.path.join(proj, "old.jsonl")
with open(stale, "w") as f:
    f.write(rec("skipped-file") + "\n")
os.utime(stale, (time.time() - 3 * 86400,) * 2)                    # not touched today: never opened

u = w.server.Usage()
assert u.scan_today() is True
pub = u.public()
models = {m["model"]: m for m in pub["models"]}
assert set(models) == {"claude-opus-5-5", "claude-sonnet-5-5"}, models
assert models["claude-opus-5-5"]["messages"] == 1, models
opus = (1000 * 4 + 500 * 20) / 1e6
sonnet = (2000 * 2 + 1000 * 10 + 1000 * .10 + 1000 * 2 * 1.25) / 1e6
assert abs(sum(m["cost"] for m in pub["models"]) - (opus + sonnet)) < 1e-6
assert w.claude_lines(pub) == (f"${opus + sonnet:,.2f}", "5.0K in · 1.5K out")

# a line added later is picked up, and a repeat scan doesn't double count
with open(os.path.join(proj, "sess.jsonl"), "a") as f:
    f.write(rec("c", out=100) + "\n")
assert u.scan_today() is True
assert u.scan_today() is False
assert {m["model"]: m["messages"] for m in u.public()["models"]}["claude-opus-5-5"] == 2

# a reset lasts while the office is open; opening it again counts all of today
u.reset()
u.scan_today()
assert u.public()["models"] == []
reopened = w.server.Usage()
reopened.scan_today()
assert {m["model"]: m["messages"] for m in reopened.public()["models"]}["claude-opus-5-5"] == 2

# an unpriced model still counts tokens and marks the cost
with open(os.path.join(proj, "sess.jsonl"), "a") as f:
    f.write(rec("d", model="claude-new-9") + "\n")
reopened.scan_today()
assert w.claude_lines(reopened.public())[0].endswith("+")
assert w.claude_lines(None)[0] == "…"

assert w.short_tokens(999) == "999" and w.short_tokens(1500) == "1.5K" and w.short_tokens(2_500_000) == "2.5M"
assert w.cursor_lines(None) == ("", "off", "right-click to turn on", 0.0)
login = {"mode": "login", "cents": 612.0, "limit": 30000.0, "resets": "2026-11-14T08:00:00.000Z", "checked": 1.0, "error": "", "email": True}
assert w.cursor_lines(login) == ("this cycle", "$6.12", "of $300.00 · resets Nov 14", 0.0204)
assert w.cursor_lines(dict(login, error="Cursor refused"))[1:3] == ("$6.12", "Cursor refused")
assert w.cursor_lines(dict(login, checked=0, cents=0, limit=0, resets="", error="no login"))[1:3] == ("—", "no login")
assert w.cursor_lines(dict(login, checked=0, cents=0, limit=0, resets=""))[1:3] == ("…", "checking Cursor")
assert w.cursor_lines({"mode": "key", "cents": 0, "checked": 0, "error": "", "email": False})[1] == "—"
print("usage widget checks passed")
