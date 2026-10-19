"""Send commands to the Claude Office from a command prompt (handy for testing).

  py office.py start "Build the login page" [--id ID] [--project NAME]
  py office.py working [ID] [--activity "Editing app.js"]
  py office.py trouble [ID] [--message "Tests failed"]
  py office.py wait    [ID] [--message "Need your OK"]
  py office.py done    [ID | all]
  py office.py list
  py office.py clear
  py office.py demo

ID defaults to the newest job. Port comes from CLAUDE_OFFICE_PORT (default 8777).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

PORT = os.environ.get("CLAUDE_OFFICE_PORT") or "8777"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def send(body: dict) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/cmd", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with OPENER.open(req, timeout=5) as r:
            return json.loads(r.read() or b"{}")
    except OSError as e:
        sys.exit(f"Can't reach the office on port {PORT} ({e}). Is server.py running?")


def show(res: dict) -> None:
    if not res.get("ok"):
        sys.exit("Error: " + str(res.get("error") or res))
    if "jobs" in res:
        if not res["jobs"]:
            print("No jobs. Everyone is on break.")
        for j in res["jobs"]:
            print(f"{j['id']:<40} {j['status']:<9} {j['title']}")
    elif res.get("worker"):
        print(f"Started {res['id']}: {res['worker']} is heading to the {res['station']}.")
    else:
        print("OK" + (f" ({res['id']})" if res.get("id") else ""))


def demo() -> None:
    """A two-minute show: three jobs that start, hit trouble, wait on you and finish."""
    steps = [
        (0, {"cmd": "start", "id": "demo-1", "title": "Refactor the billing module", "project": "demo", "area": "python"}),
        (3, {"cmd": "start", "id": "demo-2", "title": "Write tests for the date parser", "project": "demo", "area": "qa"}),
        (6, {"cmd": "start", "id": "demo-3", "title": "Update the README", "project": "demo", "area": "github"}),
        (14, {"cmd": "activity", "id": "demo-1", "activity": "Editing billing.py"}),
        (18, {"cmd": "trouble", "id": "demo-2", "message": "AssertionError: expected 2024-02-29"}),
        (28, {"cmd": "working", "id": "demo-2", "activity": "Fixing the leap-year bug"}),
        (34, {"cmd": "wait", "id": "demo-3", "message": "README is updated. Anything else?"}),
        (44, {"cmd": "wait", "id": "demo-1", "message": "Claude needs your permission to use Bash"}),
        (52, {"cmd": "done", "id": "demo-3"}),
        (58, {"cmd": "working", "id": "demo-1", "activity": "$ pytest tests"}),
        (70, {"cmd": "wait", "id": "demo-2", "message": "All tests pass. Your turn!"}),
        (80, {"cmd": "done", "id": "demo-1"}),
        (90, {"cmd": "done", "id": "demo-2"}),
    ]
    t0 = time.time()
    for at, body in steps:
        time.sleep(max(0.0, t0 + at - time.time()))
        res = send(body)
        print(f"[{at:>3}s] {body['cmd']:<8} {body['id']}: " + ("ok" if res.get("ok") else str(res.get("error"))))
    print("Demo over.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="office", description="Send commands to the Claude Office.")
    ap.add_argument("cmd", choices=["start", "working", "trouble", "wait", "done", "activity", "list", "clear", "demo"])
    ap.add_argument("arg", nargs="?", help="title for start, otherwise the job id (default: newest)")
    ap.add_argument("--id", help="job id for start (default: cli-N)")
    ap.add_argument("--project", default="cmd")
    ap.add_argument("--message", "-m")
    ap.add_argument("--activity", "-a")
    ap.add_argument("--area", help="kind of work, for the Dev Shop theme: ado, azure, github, support, sql, "
                                   "dbproj, impl, python, service, qa, hardware, tracking")
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        demo()
        return
    if a.cmd == "start":
        show(send({"cmd": "start", "title": a.arg or "Test task", "id": a.id, "project": a.project, "area": a.area}))
        return
    body = {"cmd": a.cmd, "id": a.arg or a.id or ""}
    if a.message is not None:
        body["message"] = a.message
    if a.activity is not None:
        body["activity"] = a.activity
    if a.area is not None:
        body["area"] = a.area
    show(send(body))


if __name__ == "__main__":
    main()
