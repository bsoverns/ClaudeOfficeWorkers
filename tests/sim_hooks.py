"""Simulated Claude Code sessions against a test office: checks session names on the slips and
that a lead with helpers out waits for them in the meeting room, not in the mailroom.

    py tests/sim_hooks.py

Uses port 8790 only (never the real office on 8777). Starts `src/server.py 8790` if nothing is
listening there and stops it afterwards. It clears the test office before and after. Standard
library only; scratch transcripts go in a temp folder.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

PORT = 8790
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "src", "claude_hook.py")
SERVER = os.path.join(ROOT, "src", "server.py")
BASE = f"http://127.0.0.1:{PORT}"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TMP = tempfile.mkdtemp(prefix="office-sim-")
FAILS = []


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(OPENER.open(req, timeout=5).read())


def jobs() -> dict:
    return {j["id"]: j for j in json.loads(OPENER.open(BASE + "/api/state", timeout=5).read())["jobs"]}


def up() -> bool:
    try:
        OPENER.open(BASE + "/api/ping", timeout=1).read()
        return True
    except OSError:
        return False


def hook(p: dict) -> None:
    """Run the real hook script, as Claude Code would, and check it stays silent and exits 0."""
    p.setdefault("cwd", ROOT)
    env = dict(os.environ, CLAUDE_OFFICE_PORT=str(PORT))
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(p).encode("utf-8"),
                       env=env, capture_output=True, timeout=10)
    check(r.returncode == 0 and not r.stdout and not r.stderr,
          f"hook {p.get('hook_event_name')} is silent and exits 0 (got {r.returncode}, {r.stdout!r}, {r.stderr!r})")


def transcript(name: str, *records: dict, pad: int = 0) -> str:
    """Write a scratch transcript (JSON lines); pad adds that many bytes of chatter at the end."""
    path = os.path.join(TMP, name + ".jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "hello"}}) + "\n")
        for r in records:
            f.write(json.dumps(r) + "\n")
        line = json.dumps({"type": "assistant", "message": {"content": "x" * 900}}) + "\n"
        for _ in range(pad // len(line)):
            f.write(line)
    return path


def append(path: str, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        FAILS.append(what)


def custom(t: str) -> dict:
    return {"type": "custom-title", "customTitle": t, "sessionId": "x"}


def ai(t: str) -> dict:
    return {"type": "ai-title", "aiTitle": t, "sessionId": "x"}


def test_session_names() -> None:
    print("-- session names on the slip")
    # no name yet: the prompt is the title
    s = "sim-name-none"
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Fix the flaky date test",
          "transcript_path": transcript(s)})
    check(jobs()[s]["title"] == "Fix the flaky date test", "no session name: title is the prompt")

    # the app's auto title
    s = "sim-name-ai"
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "I am testing two processes",
          "transcript_path": transcript(s, ai("Testing parallel processes"))})
    check(jobs()[s]["title"] == "Testing parallel processes", "auto title (ai-title) is used")

    # a rename wins over the auto title, the last rename wins, even ~1.3 MB back in the file
    s = "sim-name-custom"
    path = transcript(s, custom("Old name"), custom("Super Hero theme"), ai("Auto title"), pad=1_300_000)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Add a theme", "transcript_path": path})
    check(jobs()[s]["title"] == "Super Hero theme", "last rename (custom-title) wins, far back in the file")

    # a helper is named after its lead's session
    hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "h1", "agent_type": "Explore",
          "transcript_path": path})
    check(jobs()[f"{s}:h1"]["title"] == "Explore helper for: Super Hero theme", "helper title uses the session name")

    # renaming the session updates the lead and its helper on the next event
    append(path, custom("Hero HQ theme"))
    hook({"hook_event_name": "PreToolUse", "session_id": s, "tool_name": "Read",
          "tool_input": {"file_path": "README.md"}, "transcript_path": path})
    j = jobs()
    check(j[s]["title"] == "Hero HQ theme", "a rename shows on the next event")
    check(j[f"{s}:h1"]["title"] == "Explore helper for: Hero HQ theme", "a rename also renames the helper")

    # an event without a readable transcript keeps the last known name
    hook({"hook_event_name": "PreToolUse", "session_id": s, "tool_name": "Read",
          "tool_input": {"file_path": "README.md"}, "transcript_path": os.path.join(TMP, "missing.jsonl")})
    check(jobs()[s]["title"] == "Hero HQ theme", "no transcript: keeps the last known name")
    hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "h1"})


def test_lead_waits_for_helpers() -> None:
    print("-- a lead with helpers out waits in the meeting room")
    s = "sim-lead"
    path = transcript(s)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Investigate the parser bug",
          "transcript_path": path})
    hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "a1", "agent_type": "general-purpose"})
    hook({"hook_event_name": "Stop", "session_id": s, "transcript_path": path,
          "last_assistant_message": "Helper is on it; I'll report back."})
    j = jobs()[s]
    check(j["status"] == "working" and j["message"] == "", "Stop with a helper out: lead keeps working (meeting)")
    check(j["activity"] == "Waiting for 1 helper", f"activity says it waits for the helper (got {j['activity']!r})")

    hook({"hook_event_name": "Notification", "session_id": s, "transcript_path": path,
          "notification_type": "idle_prompt", "message": "Claude is waiting for your input"})
    check(jobs()[s]["status"] == "working", "idle notification with a helper out is ignored")
    hook({"hook_event_name": "Notification", "session_id": s, "transcript_path": path,
          "message": "Claude is waiting for your input"})
    check(jobs()[s]["status"] == "working", "idle notification without notification_type is ignored too")
    hook({"hook_event_name": "Notification", "session_id": s, "transcript_path": path,
          "notification_type": "permission_prompt", "message": "Claude needs your permission to use Bash"})
    check(jobs()[s]["status"] == "waiting", "a permission request still sends the lead to the mailroom")

    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "go on", "transcript_path": path})
    hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "a1"})
    hook({"hook_event_name": "Stop", "session_id": s, "transcript_path": path, "last_assistant_message": "All done."})
    j = jobs()[s]
    check(j["status"] == "waiting" and j["message"] == "All done.", "Stop with no helpers left: lead waits for you")

    # background helpers: the lead's turn ends first; it only waits on you once the last one is back
    s = "sim-lead-bg"
    path = transcript(s)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Review the PR", "transcript_path": path})
    hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "c1", "agent_type": "Explore"})
    hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "c2", "agent_type": "Explore"})
    hook({"hook_event_name": "Stop", "session_id": s, "transcript_path": path,
          "last_assistant_message": "Two reviewers are on it."})
    j = jobs()[s]
    check(j["status"] == "working" and j["activity"] == "Waiting for 2 helpers",
          "turn over with 2 helpers out: working, not waiting on you (no alert, no mailroom)")
    hook({"hook_event_name": "Notification", "session_id": s, "transcript_path": path,
          "notification_type": "idle_prompt", "message": "Claude is waiting for your input"})
    hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "c1"})
    j = jobs()[s]
    check(j["status"] == "working" and j["activity"] == "Waiting for 1 helper", "one helper back: still waiting on the other")
    hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "c2"})
    j = jobs()[s]
    check(j["status"] == "waiting" and j["message"] == "Two reviewers are on it.",
          "last helper back after the lead stopped: now waiting on you (mailroom)")

    # async hooks out of order: the Stop lands first, then the SubagentStart that happened before it
    s = "sim-lead-late"
    now = time.time()
    post("/api/hook", {"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Plan it", "ts": now - 3})
    post("/api/hook", {"hook_event_name": "Stop", "session_id": s, "last_assistant_message": "Sent a helper.", "ts": now})
    check(jobs()[s]["status"] == "waiting", "late case: the early Stop puts the lead in the mailroom")
    post("/api/hook", {"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "b1",
                       "agent_type": "Plan", "ts": now - 1})
    j = jobs()[s]
    check(j["status"] == "working" and j["activity"] == "Waiting for 1 helper",
          "late SubagentStart brings the lead back to the meeting")
    post("/api/hook", {"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "b1", "ts": time.time()})
    j = jobs()[s]
    check(j["status"] == "waiting" and j["message"] == "Sent a helper.", "late case: waits on you once the helper is back")

    # a SubagentStart that lands after its own SubagentStop is ignored (no helper that never stops)
    post("/api/hook", {"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "b1",
                       "agent_type": "Plan", "ts": now - 1})
    j = jobs()
    check(f"{s}:b1" not in j and j[s]["status"] == "waiting", "start after its own stop: ignored, lead still waits on you")

    # a permission request after the turn ended: the last helper back still hands the turn to you
    s = "sim-lead-perm"
    path = transcript(s)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Build it", "transcript_path": path})
    hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "e1", "agent_type": "general-purpose"})
    hook({"hook_event_name": "Stop", "session_id": s, "transcript_path": path, "last_assistant_message": "Builder is on it."})
    hook({"hook_event_name": "Notification", "session_id": s, "transcript_path": path,
          "notification_type": "permission_prompt", "message": "Claude needs your permission to use Bash"})
    check(jobs()[s]["status"] == "waiting", "permission while the helper works: mailroom")
    hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "e1"})
    j = jobs()[s]
    check(j["status"] == "waiting" and j["message"] == "Builder is on it.",
          "after the permission, the last helper back shows the lead's own stop message")
    hook({"hook_event_name": "SubagentStop", "session_id": s})
    check(jobs()[s]["status"] == "waiting", "SubagentStop without agent_id changes nothing")


def test_quiet_helper_releases_lead() -> None:
    """A helper whose SubagentStop never lands: once it is quiet for HELPER_QUIET_MINUTES the
    reaper hands the lead's turn to you. Runs on an in-process Office (no waiting 10 minutes)."""
    print("-- a lost SubagentStop does not keep the lead from waiting on you")
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import server
    office = server.Office()
    s = "sim-orphan"
    office.handle_hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Go"})
    office.handle_hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "o1", "agent_type": "Explore"})
    office.handle_hook({"hook_event_name": "Stop", "session_id": s, "last_assistant_message": "Explorer sent."})
    check(office.jobs[s]["status"] == "working", "orphan: lead waits on its helper at first")
    office.reap()
    check(office.jobs[s]["status"] == "working", "orphan: a helper heard from lately still holds the lead")
    office.jobs[f"{s}:o1"]["updated"] -= server.HELPER_QUIET_MINUTES * 60 + 5
    office.reap()
    j = office.jobs[s]
    check(j["status"] == "waiting" and j["message"] == "Explorer sent.", "orphan: quiet helper, the reaper hands the turn to you")
    office.handle_hook({"hook_event_name": "Stop", "session_id": s, "last_assistant_message": "Again."})
    check(office.jobs[s]["status"] == "waiting", "orphan: a later Stop ignores the quiet helper")


def meta(sid: str, aid: str, description: str) -> None:
    """The subagent meta file Claude Code writes beside the lead's transcript."""
    folder = os.path.join(TMP, sid, "subagents")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"agent-{aid}.meta.json"), "w", encoding="utf-8") as f:
        json.dump({"agentType": "general-purpose", "description": description, "toolUseId": "t-" + aid}, f)


def worker_of(jid: str) -> object:
    j = jobs().get(jid)
    return j["worker"] if j else None


def start_helper(s: str, aid: str, path: str, kind: str = "general-purpose") -> object:
    hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": aid, "agent_type": kind,
          "transcript_path": path})
    return worker_of(f"{s}:{aid}")


def stop_helper(s: str, aid: str, path: str) -> None:
    hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": aid, "transcript_path": path})


def test_helper_characters(restart) -> None:
    print("-- each subagent gets its own character for the session")
    post("/api/cmd", {"cmd": "clear"})

    # a continued subagent (SendMessage) fires a new SubagentStart with the same agent_id
    s = "sim-cont"
    path = transcript(s)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Go", "transcript_path": path})
    start_helper(s, "x1", path)
    hook({"hook_event_name": "Stop", "session_id": s, "transcript_path": path, "last_assistant_message": "Sent x1."})
    stop_helper(s, "x1", path)
    start_helper(s, "x1", path)
    hook({"hook_event_name": "PreToolUse", "session_id": s, "agent_id": "x1", "tool_name": "Read",
          "tool_input": {"file_path": "notes.txt"}, "transcript_path": path})
    j = jobs()
    check(f"{s}:x1" in j and "notes.txt" in j[f"{s}:x1"]["activity"] and "notes.txt" not in j[s]["activity"],
          "continued subagent: back as a helper, its tool call lands on the helper, not the lead")
    post("/api/cmd", {"cmd": "clear"})

    # sequential unnamed helpers: a different character each, never the lead's
    s = "sim-seq"
    path = transcript(s)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Go", "transcript_path": path})
    lead = worker_of(s)
    seen = []
    for aid in ("q1", "q2", "q3"):
        seen.append(start_helper(s, aid, path))
        stop_helper(s, aid, path)
    check(len(set(seen)) == 3 and lead not in seen and None not in seen,
          f"3 sequential helpers: 3 different characters, none the lead's ({lead} / {seen})")

    # concurrent helpers in two sessions: all distinct
    ws = [lead]
    for s2 in ("sim-par-a", "sim-par-b"):
        p2 = transcript(s2)
        hook({"hook_event_name": "UserPromptSubmit", "session_id": s2, "prompt": "Go", "transcript_path": p2})
        ws.append(worker_of(s2))
        ws += [start_helper(s2, aid, p2) for aid in ("r1", "r2", "r3")]
    check(None not in ws and len(set(ws)) == len(ws), f"concurrent helpers in two sessions: all distinct ({ws})")
    post("/api/cmd", {"cmd": "clear"})

    # named agents: same name -> same character, another name -> another one
    s = "sim-named"
    path = transcript(s)
    hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Go", "transcript_path": path})
    meta(s, "n1", "Neo: fix three bugs")
    neo = start_helper(s, "n1", path)
    j = jobs()[f"{s}:n1"]
    check(j["agent"] == "Neo" and j["title"] == "Neo: fix three bugs", "named agent: slip shows its name and description")
    stop_helper(s, "n1", path)
    meta(s, "n2", "Neo: round two fixes")
    check(start_helper(s, "n2", path) == neo, "a second agent named Neo gets Neo's character")
    meta(s, "h1", "Hawk: review the diff")
    hawk = start_helper(s, "h1", path)
    check(hawk not in (None, neo), "an agent named Hawk gets a different character")
    stop_helper(s, "n2", path)
    stop_helper(s, "h1", path)
    check(start_helper(s, "h1", path) == hawk, "a continued agent keeps its character")
    stop_helper(s, "h1", path)
    # the name can also come from the lead's Agent call when the meta file isn't there yet
    hook({"hook_event_name": "PreToolUse", "session_id": s, "tool_name": "Agent", "transcript_path": path,
          "tool_input": {"description": "Sage: find the root cause", "subagent_type": "general-purpose"}})
    start_helper(s, "g1", path)
    check(jobs()[f"{s}:g1"]["agent"] == "Sage", "name from the lead's Agent call before the meta file exists")
    stop_helper(s, "g1", path)

    def call(desc: str, tuid: str = "", aid: str = "") -> None:
        body = {"hook_event_name": "PreToolUse", "session_id": s, "tool_name": "Agent", "tool_use_id": tuid,
                "tool_input": {"description": desc, "subagent_type": "general-purpose"}}
        post("/api/hook", dict(body, agent_id=aid) if aid else body)

    def start(aid: str, tuid: str = "") -> dict:
        post("/api/hook", {"hook_event_name": "SubagentStart", "session_id": s, "agent_id": aid,
                           "agent_type": "general-purpose", "agent_tool_use_id": tuid})
        return jobs()[f"{s}:{aid}"]

    # a denied Agent call leaves a stale entry; the next helper is matched by its tool_use_id
    call("Ghost: never started", "tu-ghost")
    call("Sage: second look", "tu-sage2")
    check(start("g2", "tu-sage2")["agent"] == "Sage", "matched by tool_use_id, not by the stale denied call")
    # a new prompt drops the stale call
    post("/api/hook", {"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "next"})
    check(start("g3")["agent"] == "", "a new prompt clears Agent calls that never started")
    # a guessed name (no id) is dropped when the description has no "Name:"
    call("Pip: guessed")
    g4 = start("g4")
    post("/api/hook", {"hook_event_name": "PreToolUse", "session_id": s, "agent_id": "g4", "tool_name": "Read",
                       "tool_input": {"file_path": "a.txt"}, "agent_description": "plain task without a name"})
    j = jobs()[f"{s}:g4"]
    check(g4["agent"] == "Pip" and j["agent"] == "" and j["title"] == "plain task without a name"
          and j["worker"] == g4["worker"], "a guessed name gives way to a nameless description; same character")
    # a helper's own (nested) Agent call is not queued on the lead
    call("Nested: deep dive", "tu-nested", aid="g4")
    check(start("g5")["agent"] == "", "a helper's nested Agent call does not name the lead's next helper")
    for aid in ("g2", "g3", "g4", "g5"):
        stop_helper(s, aid, path)

    if restart:
        restart()
        meta(s, "n3", "Neo: after the restart")
        check(start_helper(s, "n3", path) == neo, "after a restart Neo still gets Neo's character")
        stop_helper(s, "n3", path)
    else:
        print("skip  restart check (a server was already running on 8790)")


def test_helper_links_freed() -> None:
    """In-process: the links go when the session ends, and more agents than characters queue."""
    print("-- subagent characters are freed when the session ends; overflow queues")
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import server
    office = server.Office()
    s = "sim-free"
    office.handle_hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Go"})
    office.handle_hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": "f1",
                        "agent_type": "general-purpose", "agent_description": "Neo: one"})
    office.handle_hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "f1"})
    check(any(l["sid"] == s for l in office.links.values()), "links exist while the session lives")
    office.handle_hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "thanks"})
    check(not any(l["sid"] == s for l in office.links.values()), "after done, the session's links are gone")

    office = server.Office()
    s = "sim-many"
    office.handle_hook({"hook_event_name": "UserPromptSubmit", "session_id": s, "prompt": "Go"})
    for i in range(20):
        office.handle_hook({"hook_event_name": "SubagentStart", "session_id": s, "agent_id": f"m{i}",
                            "agent_type": "general-purpose"})
    staffed = [j["worker"] for j in office.jobs.values() if j["worker"] is not None]
    check(len(staffed) == len(server.ROSTER) == len(set(staffed)), "20 agents + lead: 16 characters busy, no doubles")
    check(sum(j["worker"] is None for j in office.jobs.values()) == 21 - len(server.ROSTER), "the rest queue")
    office.handle_hook({"hook_event_name": "SubagentStop", "session_id": s, "agent_id": "m0"})
    staffed = [j["worker"] for j in office.jobs.values() if j["worker"] is not None]
    check(len(staffed) == len(set(staffed)) == len(server.ROSTER), "a freed character goes to a queued agent")


SERVER_PROC = None


def start_server() -> None:
    global SERVER_PROC
    SERVER_PROC = subprocess.Popen([sys.executable, SERVER, str(PORT)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if up():
            return
        time.sleep(0.1)


def stop_server() -> None:
    if SERVER_PROC:
        SERVER_PROC.terminate()
        SERVER_PROC.wait(timeout=5)


def main() -> int:
    ours = not up()
    if ours:
        start_server()
    try:
        post("/api/cmd", {"cmd": "clear"})
        test_session_names()
        test_lead_waits_for_helpers()
        test_helper_characters((lambda: (stop_server(), start_server())) if ours else None)
        post("/api/cmd", {"cmd": "clear"})
        test_quiet_helper_releases_lead()
        test_helper_links_freed()
    finally:
        if ours:
            stop_server()
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
