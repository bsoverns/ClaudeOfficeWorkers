"""Simulated Cursor chats against a test Cursor office: checks the event translation, the hook's
JSON replies, the installer and that the Claude hook stays out of Cursor's events.

    py tests/sim_cursor_hooks.py

Uses port 8791 only (never the real offices on 8777 and 8778). Starts `src/server.py --cursor 8791`
and stops it afterwards. It clears the test office first. Payloads follow Cursor's hooks docs; this
doesn't run Cursor itself. Standard library only; scratch files go in a temp folder.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

PORT = 8791
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BASE = f"http://127.0.0.1:{PORT}"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TMP = tempfile.mkdtemp(prefix="office-cursor-sim-")
FAILS = []
BLOCKING = {"preToolUse", "subagentStart", "beforeShellExecution", "beforeMCPExecution", "beforeReadFile", "beforeTabFileRead"}


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        FAILS.append(what)


def state() -> dict:
    return json.loads(OPENER.open(BASE + "/api/state", timeout=5).read())


def job(jid: str) -> dict:
    return next((j for j in state()["jobs"] if j["id"] == jid), {})


def up() -> bool:
    try:
        OPENER.open(BASE + "/api/ping", timeout=1).read()
        return True
    except OSError:
        return False


def run(script: str, payload: bytes, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, os.path.join(SRC, script)], input=payload, capture_output=True,
                          timeout=10, env=dict(os.environ, **env))


def hook(event: str, **fields: object) -> object:
    """Run the real hook, as Cursor would. Returns its parsed reply; it must be JSON with exit 0."""
    p = {"hook_event_name": event, "conversation_id": "chat-1", "generation_id": "g", "cursor_version": "2.0",
         "workspace_roots": ["C:/work/shop"], "transcript_path": None, **fields}
    r = run("cursor_hook.py", json.dumps(p).encode("utf-8"), CURSOR_OFFICE_PORT=str(PORT))
    try:
        reply = json.loads(r.stdout)
    except ValueError:
        reply = None
    check(r.returncode == 0 and isinstance(reply, dict) and not r.stderr,
          f"{event} exits 0 with a JSON reply (got {r.returncode}, {r.stdout!r}, {r.stderr!r})")
    return reply


def test_chat() -> None:
    print("-- a chat from prompt to done")
    check(state()["product"] == "Cursor", "the office says it is the Cursor office")
    check(hook("beforeSubmitPrompt", prompt="Fix the login page") == {"continue": True}, "the prompt is explicitly let through")
    j = job("chat-1")
    check(j.get("status") == "working" and j.get("title") == "Fix the login page", f"prompt starts a job ({j})")
    check(j.get("project") == "shop", f"project comes from workspace_roots ({j.get('project')})")
    check(hook("postToolUse", tool_name="Shell", tool_input={"command": "npm test", "working_directory": "C:/x"},
               tool_output='{"stdout":"SECRET"}', cwd="C:/work/shop") == {}, "a tool reply adds no context")
    check(job("chat-1").get("activity") == "$ npm test", f"Shell reads as a command ({job('chat-1').get('activity')})")
    hook("postToolUse", tool_name="Read", tool_input={"file_path": "C:/work/shop/login.py"})
    check(job("chat-1").get("activity") == "Reading login.py", f"Read names the file ({job('chat-1').get('activity')})")
    hook("postToolUseFailure", tool_name="Shell", tool_input={}, error_message="exit code 1", failure_type="error")
    j = job("chat-1")
    check(j.get("status") == "trouble" and j.get("message") == "exit code 1", f"a failed tool goes to troubleshooting ({j.get('status')})")
    hook("postToolUseFailure", tool_name="Shell", tool_input={}, error_message="", failure_type="error", is_interrupt=True)
    check(job("chat-1").get("status") == "waiting", "an interrupt waits on you")
    hook("postToolUse", tool_name="Grep", tool_input={"pattern": "login"})
    check(job("chat-1").get("status") == "working", "the next tool goes back to work")
    check(hook("stop", status="completed", loop_count=0) == {}, "stop sets no follow-up message")
    check(job("chat-1").get("status") == "waiting", "stop waits on you")
    hook("stop", status="aborted", loop_count=0)
    check("stopped me" in job("chat-1").get("message", ""), "an aborted stop says so")
    hook("sessionEnd", session_id="chat-1", reason="window_close", duration_ms=1)
    check(bool(job("chat-1")), "closing the window keeps the job waiting")
    hook("sessionEnd", session_id="chat-1", reason="user_close", duration_ms=1)
    check(not job("chat-1"), "closing the chat yourself ends it")
    hook("beforeSubmitPrompt", conversation_id="chat-2", prompt="Add a page")
    hook("beforeSubmitPrompt", conversation_id="chat-2", prompt="thanks")
    check(not job("chat-2"), 'saying "thanks" ends it')


def test_robust() -> None:
    print("-- never in Cursor's way")
    r = run("cursor_hook.py", b"not json", CURSOR_OFFICE_PORT=str(PORT))
    check(r.returncode == 0 and r.stdout == b"{}", f"bad input still exits 0 with JSON ({r.returncode}, {r.stdout!r})")
    p = json.dumps({"hook_event_name": "beforeSubmitPrompt", "conversation_id": "bom", "prompt": "With a BOM"}).encode("utf-8")
    r = run("cursor_hook.py", b"\xef\xbb\xbf" + p, CURSOR_OFFICE_PORT=str(PORT))
    check(job("bom").get("title") == "With a BOM", f"input with PowerShell's BOM still reports ({r.stdout!r})")
    t = time.time()
    p = json.dumps({"hook_event_name": "postToolUse", "conversation_id": "x", "tool_name": "Read"}).encode("utf-8")
    r = run("cursor_hook.py", p, CURSOR_OFFICE_PORT="8792")
    check(r.returncode == 0 and r.stdout == b"{}", "a closed office still exits 0 with JSON")
    print(f"      (hook with the office closed took {time.time() - t:.2f}s)")
    before = len(state()["jobs"])
    r = run("claude_hook.py", json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "leak", "prompt": "Hi",
                                          "cursor_version": "2.0"}).encode("utf-8"), CLAUDE_OFFICE_PORT=str(PORT))
    check(r.returncode == 0 and len(state()["jobs"]) == before, "the Claude hook ignores events that come from Cursor")


def test_installer() -> None:
    print("-- installer on a scratch project")
    sys.path.insert(0, SRC)
    import install_cursor_hooks as inst
    path = os.path.join(TMP, ".cursor", "hooks.json")
    os.makedirs(os.path.dirname(path))
    theirs = {"command": "./mine.sh", "timeout": 9}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "extra": True, "hooks": {"stop": [theirs], "afterFileEdit": [theirs]}}, f)
    inst.install(TMP)
    inst.install(TMP)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    check(cfg["extra"] is True and theirs in cfg["hooks"]["stop"] and theirs in cfg["hooks"]["afterFileEdit"], "other hooks and settings are kept")
    check(all(sum(inst.ours(e) for e in cfg["hooks"][ev]) == 1 for ev in inst.EVENTS), "installing twice adds each hook once")
    check(not BLOCKING & set(cfg["hooks"]), "no permission hook is installed")
    inst.install(TMP, uninstall=True)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    check(cfg["hooks"] == {"stop": [theirs], "afterFileEdit": [theirs]} and cfg["version"] == 1, "uninstall leaves only the other hooks")
    if os.name == "nt":
        p = json.dumps({"hook_event_name": "beforeSubmitPrompt", "conversation_id": "ps", "prompt": "Through PowerShell"})
        r = subprocess.run(["powershell", "-NoProfile", "-Command", f"$input | {inst.hook_command()}"], input=p.encode("utf-8"),
                           capture_output=True, timeout=30, env=dict(os.environ, CURSOR_OFFICE_PORT=str(PORT)))
        check(r.stdout.strip() == b'{"continue": true}' and job("ps").get("title") == "Through PowerShell",
              f"the installed command runs through PowerShell ({r.stdout!r}, {r.stderr[:200]!r}, {job('ps')})")


def test_cost() -> None:
    print("-- Cursor cost, against a fake API")
    sys.path.insert(0, SRC)
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import server as srv
    seen = []
    answer = {"status": 200}

    class Fake(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.headers.get("Authorization"), body))
            more = body["page"] < 2
            out = {"usageEvents": [{"chargedCents": 150}, {"chargedCents": 25.5}, {"model": "no charge field"}] if more else [{"chargedCents": 100}],
                   "pagination": {"hasNextPage": more}}
            self.send_response(answer["status"])
            self.end_headers()
            self.wfile.write(json.dumps(out).encode("utf-8"))

        def log_message(self, *a):
            pass

    api = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    srv.CURSOR_USAGE_URL = f"http://127.0.0.1:{api.server_port}/"
    cost = srv.CursorCost()
    check(cost.public() is None, "no key: cost is off")
    cost.saw_hook({"user_email": "me@work.test"})
    check(not cost.email, "no key: a hook's email isn't kept")
    cost.key = "SECRET-KEY"
    check(cost.public() == {"mode": "key", "cents": 0, "checked": 0, "error": "", "email": False}, "with a key, it waits for your email")
    cost.saw_hook({"user_email": "me@work.test"})
    check(cost.email == "me@work.test" and cost.wake.is_set(), "the first hook names you and starts a check")
    cost.check()
    check(cost.public()["cents"] == 275.5, f"all pages add up ({cost.public()})")
    check(all(b["email"] == "me@work.test" for _, b in seen) and [b["page"] for _, b in seen] == [1, 2], "it only ever asks for your email")
    check(seen[0][0] == "Basic U0VDUkVULUtFWTo=", "the key goes as Basic auth with an empty password")
    check("SECRET" not in json.dumps(cost.public()), "the key never reaches the page")
    answer["status"] = 401
    cost.check()
    p = cost.public()
    check(p["cents"] == 275.5 and "refused" in p["error"], f"a refused key keeps the last number and says why ({p})")
    answer["status"] = 200
    cost.check()
    check(cost.public()["error"] == "", "the next good check clears the error")
    cost.day = "2000-01-01"
    check(cost.public()["cents"] == 0, "a new day doesn't show yesterday's cost")
    srv.CURSOR_USAGE_URL = "http://127.0.0.1:1/"
    cost.check()
    check("reach" in cost.public()["error"], f"no network is reported, not raised ({cost.public()['error']})")
    api.shutdown()


def fake_login(path: str, token: str | None) -> None:
    """A scratch copy of Cursor's store, in its real shape."""
    import sqlite3
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE ItemTable (key TEXT UNIQUE, value BLOB)")
    if token:
        db.execute("INSERT INTO ItemTable VALUES ('cursorAuth/accessToken', ?)", (token,))
    db.commit()
    db.close()


def test_cursor_app() -> None:
    print("-- CursorOffice.exe is always the Cursor office")
    sys.path.insert(0, SRC)
    import app
    check(app.cursor_args([]) == ["--cursor"], "no arguments opens the Cursor office")
    check(app.cursor_args(["--server", "8791"]) == ["--server", "--cursor", "8791"], "--server is its server")
    check(app.cursor_args(["--install", "--uninstall"]) == ["--cursor-install", "--uninstall"], "--install connects Cursor, not Claude Code")
    check(app.cursor_args(["--hook"]) == ["--cursor-hook"], "--hook is the Cursor hook")
    check(app.cursor_args(["--cursor-hook"]) == ["--cursor-hook"], "the installed hook command works as it is")
    check(app.cursor_args(["--cost-check"]) == ["--cursor-cost-check"], "--cost-check is the cost check")


def test_login_cost() -> None:
    print("-- Cursor cost through your login, against fakes")
    sys.path.insert(0, SRC)
    import base64
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import server as srv
    part = base64.urlsafe_b64encode(json.dumps({"sub": "auth0|user_abc", "email": "me@work.test"}).encode()).decode().rstrip("=")
    token = f"head.{part}.SIGNATURE"
    seen = []
    answer = {"summary": {}, "period": {}, "status": 200, "redirect": False}

    class Fake(BaseHTTPRequestHandler):
        def respond(self, out):
            if answer["redirect"]:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{api.server_port}/stolen")
                self.end_headers()
                return
            self.send_response(answer["status"])
            self.end_headers()
            self.wfile.write(json.dumps(out).encode("utf-8"))

        def do_GET(self):
            seen.append((self.path, dict(self.headers)))
            self.respond(answer["summary"])

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            seen.append((self.path, dict(self.headers)))
            self.respond(answer["period"])

        def log_message(self, *a):
            pass

    api = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    srv.CURSOR_SUMMARY_URL = f"http://127.0.0.1:{api.server_port}/summary"
    srv.CURSOR_PERIOD_URL = f"http://127.0.0.1:{api.server_port}/period"
    db = os.path.join(TMP, "with space", "state.vscdb")
    srv.cursor_state_db = lambda: db
    cost = srv.CursorCost()
    cost.login = True

    cost.check_login()
    check("wasn't found" in cost.error and not seen, f"no Cursor on the PC is reported, with no calls ({cost.error})")
    fake_login(db, None)
    cost.check_login()
    check("isn't logged in" in cost.error and not seen, f"logged out is reported, with no calls ({cost.error})")
    fake_login(db, '"not-a-jwt"')
    cost.check_login()
    check("format" in cost.error and "not-a-jwt" not in cost.error and not seen, f"a strange login is reported, not shown ({cost.error})")

    fake_login(db, f'"{token}"')
    check(srv.read_cursor_login() == (token, "user_abc"), "the login and user id come from Cursor's store")
    answer["summary"] = {"membershipType": "enterprise", "billingCycleEnd": "2026-12-01T00:00:00.000Z",
                         "individualUsage": {"overall": {"used": 200, "limit": 30000}, "plan": {"used": 5, "limit": 7}},
                         "teamUsage": {"pooled": {"used": 999999, "limit": 9999999}}}
    cost.check_login()
    p = cost.public()
    check(p["mode"] == "login" and p["cents"] == 200 and p["limit"] == 30000 and not p["error"], f"enterprise spend is yours, not the team's ({p})")
    head = dict(seen)
    check(f"WorkosCursorSessionToken=user_abc%3A%3A{token}" == head["/summary"].get("Cookie"), "the summary call sends the login as Cursor's cookie")
    check(head["/period"].get("Authorization") == f"Bearer {token}", "the period call sends it as a bearer token")
    check(token not in json.dumps(p) and "SIGNATURE" not in json.dumps(p), "the login never reaches the page")
    answer["summary"] = {"individualUsage": {"plan": {"used": 100, "limit": 2000}, "onDemand": {"used": 50}}}
    cost.check_login()
    check(cost.public()["cents"] == 150 and cost.public()["limit"] == 2000, "other plans add plan and on-demand")
    answer["summary"], answer["period"] = {}, {"planUsage": {"totalSpend": 75, "limit": 2000}}
    cost.check_login()
    check(cost.public()["cents"] == 75, "the period call is the fallback")
    answer["status"] = 401
    cost.check_login()
    p = cost.public()
    check(p["cents"] == 75 and "refused" in p["error"], f"an expired login keeps the last number and says why ({p['error']})")
    answer["status"], answer["redirect"] = 200, True
    del seen[:]
    cost.check_login()
    check(not any(path == "/stolen" for path, _ in seen), "the login is never sent on through a redirect")
    answer["redirect"] = False
    answer["summary"], answer["period"] = {"individualUsage": {"overall": {"used": 200, "limit": 30000}}, "ownerEmail": "me@work.test", "userId": 7, "note": "hi",
                                                 "teamUsage": {"onDemand": {"used": 26954}}, "pooledUsed": 41234}, {}
    report = srv.cursor_cost_report()
    check("$2.00 of $300.00" in report, f"the check says what it would show ({report.splitlines()[-1]})")
    check(not any(s in report for s in (token, "SIGNATURE", "user_abc", "me@work.test", "ownerEmail", "userId", "hi")), "the check holds no login, email or ids")
    check(not any(s in report for s in ("teamUsage", "26954", "pooledUsed", "41234")), "the check leaves out the team's spend")
    check('"individualUsage": {"overall": {"used": 200, "limit": 30000}}' in report, "the check shows your own spend fields")
    check(len(srv.cursor_cost_report().splitlines()) == 4, "the check reports both calls")

    home = os.path.join(TMP, "settings")
    srv.data_dir = lambda: home
    os.environ.pop("CURSOR_ADMIN_KEY", None)
    on = srv.CursorCost()
    check(on.public() is None, "off by default")
    on.set_login(True)
    check(on.public() is not None, "the checkbox turns it on")
    start = srv.CursorCost()
    with open(os.path.join(home, "cursor-cost.json"), encoding="utf-8") as f:
        start.login = json.load(f)["login"]
    with open(os.path.join(home, "cursor-cost.json"), encoding="utf-8") as f:
        saved = f.read()
    check(start.login is True and "SIGNATURE" not in saved and "user_abc" not in saved, f"it's on again at the next start, with no login saved ({saved})")
    on.set_login(False)
    check(on.public() is None, "and off again")
    api.shutdown()


def main() -> None:
    if up():
        sys.exit(f"Something is already listening on port {PORT}; stop it first.")
    server = subprocess.Popen([sys.executable, os.path.join(SRC, "server.py"), "--cursor", str(PORT)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if up():
                break
            time.sleep(0.1)
        req = urllib.request.Request(BASE + "/api/cmd", data=b'{"cmd": "clear"}', headers={"Content-Type": "application/json"}, method="POST")
        OPENER.open(req, timeout=5).read()
        test_chat()
        test_robust()
        test_installer()
        test_cost()
        test_login_cost()
        test_cursor_app()
    finally:
        server.terminate()
        shutil.rmtree(TMP, ignore_errors=True)
    print("all passed" if not FAILS else f"{len(FAILS)} failed:\n  " + "\n  ".join(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
