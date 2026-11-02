"""Cursor hook -> the Cursor office (the second office process; claude_hook.py feeds the first).

Cursor runs this for each hooked event and pipes the event JSON to stdin. We turn it into the
office's own event names and POST it to the Cursor office, port 8778 by default. Only events
that can't block Cursor are hooked (see EVENTS in install_cursor_hooks.py): on a permission
hook such as preToolUse, Cursor blocks the action if the output isn't valid JSON, and an
"allow" could skip an approval you'd otherwise be asked for. Cursor has no async hooks and waits
for this process, so the post gives up quickly. Always exits 0, even on errors.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time

from claude_hook import read_stdin

DEFAULT_PORT = "8778"
POST_TIMEOUT = 0.5   # same as claude_hook.py: any shorter and a busy PC can lose the event that starts a job
EVENT_NAMES = {"beforeSubmitPrompt": "UserPromptSubmit", "postToolUse": "PreToolUse",
               "postToolUseFailure": "PostToolUseFailure", "stop": "Stop", "sessionEnd": "SessionEnd"}
TOOL_NAMES = {"Shell": "Bash"}   # the names the office's speech bubbles know
KEEP_INPUT = ("command", "pattern", "query", "url", "description")
PATH_KEYS = ("file_path", "path", "target_file")
STOP_MESSAGES = {"aborted": "You stopped me — what next?", "error": "Something went wrong — your turn"}
USER_CLOSED = "prompt_input_exit"   # the end reason the office treats as "you closed the session"


def tool_input(ti: object) -> dict:
    """Just the tool fields the speech bubble uses, each cut short. The rest stays out of the post."""
    if not isinstance(ti, dict):
        return {}
    out = {k: str(ti[k])[:200] for k in KEEP_INPUT if k in ti}
    path = next((ti[k] for k in PATH_KEYS if ti.get(k)), None)
    if path:
        out["file_path"] = str(path)[:200]
    return out


def translate(p: dict, ts: float) -> dict | None:
    """The office's event for a Cursor event, or None if it isn't one we report. Built field by
    field, so tool output, file contents and the transcript path never leave this script. Without
    a transcript the token meter stays out of it: Cursor's transcripts aren't Claude's format."""
    ev = EVENT_NAMES.get(str(p.get("hook_event_name") or ""))
    sid = p.get("conversation_id") or p.get("session_id")
    if not ev or not sid:
        return None
    roots = p.get("workspace_roots")
    cwd = p.get("cwd") or (roots[0] if isinstance(roots, list) and roots else "")
    out = {"hook_event_name": ev, "session_id": str(sid), "cwd": str(cwd), "ts": ts}
    if isinstance(p.get("user_email"), str):
        out["user_email"] = p["user_email"]   # whose cost to ask for, if you've turned cost on (server.py: CursorCost)
    if ev == "UserPromptSubmit":
        out["prompt"] = str(p.get("prompt") or "")[:2000]
    elif ev == "PreToolUse":
        name = str(p.get("tool_name") or "")
        out["tool_name"] = TOOL_NAMES.get(name, name)
        out["tool_input"] = tool_input(p.get("tool_input"))
    elif ev == "PostToolUseFailure":
        out["error"] = str(p.get("error_message") or "")[:2000]
        out["is_interrupt"] = bool(p.get("is_interrupt"))
    elif ev == "Stop":
        out["last_assistant_message"] = STOP_MESSAGES.get(str(p.get("status") or ""), "")
    elif ev == "SessionEnd":
        reason = str(p.get("reason") or "")
        out["reason"] = USER_CLOSED if reason == "user_close" else reason
    return out


def reply(event: str) -> None:
    """Valid JSON that changes nothing: {} adds no context, sets no follow-up message and
    (explicitly, on the one hooked event that could) doesn't stop your prompt."""
    try:
        sys.stdout.write(json.dumps({"continue": True} if event == "beforeSubmitPrompt" else {}))
        sys.stdout.flush()
    except Exception:
        pass


def post(port: str, body: bytes) -> None:
    """POST to the office over a plain socket. urllib would load http, email and ssl (its DLLs
    too) on every event, and a new process starts for each one: that delay is what you see in
    the office, since workers only move once this arrives."""
    head = (f"POST /api/hook HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode("ascii")
    with socket.create_connection(("127.0.0.1", int(port)), timeout=POST_TIMEOUT) as s:
        s.sendall(head + body)
        s.recv(1)


def main() -> None:
    ts = time.time()
    event = ""
    try:
        # -sig: PowerShell, which runs Cursor's hooks on Windows, can put a BOM in front of what it pipes
        p = json.loads(read_stdin().decode("utf-8-sig", "replace") or "{}")
        if not isinstance(p, dict):
            return
        event = str(p.get("hook_event_name") or "")
        out = translate(p, ts)
        if out:
            post(os.environ.get("CURSOR_OFFICE_PORT") or DEFAULT_PORT, json.dumps(out).encode("utf-8"))
    finally:
        reply(event)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
