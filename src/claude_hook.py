"""Claude Code hook -> Claude Office Workers.

Claude Code runs this for each hooked event and pipes the event JSON to stdin. We trim it
and POST it to the office server. It must never get in Claude's way: it prints nothing
(UserPromptSubmit output would be added to Claude's context), swallows every error and
always exits 0. If the office isn't running, the post fails instantly and nothing happens.
"""
import json
import os
import sys
import time
import urllib.request

KEEP_INPUT = ("command", "file_path", "pattern", "query", "url", "description", "subagent_type", "name")
TITLE_TAIL = 2 * 1024 * 1024  # how much of the transcript's end to search for the session name
TITLE_KINDS = ((b'"custom-title"', "custom-title", "customTitle"),  # a rename in the app
               (b'"ai-title"', "ai-title", "aiTitle"))                # the app's own title


def session_title(path: object) -> str:
    """The session's name as the Claude app shows it: the last rename, else its auto title.
    Reads only the end of the transcript (JSON lines); returns "" if there is none."""
    if not isinstance(path, str) or not path:
        return ""
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - TITLE_TAIL))
        data = f.read()
    for needle, kind, field in TITLE_KINDS:
        i = data.rfind(needle)
        while i >= 0:
            start = data.rfind(b"\n", 0, i) + 1
            end = data.find(b"\n", i)
            try:
                rec = json.loads(data[start:end if end >= 0 else len(data)].decode("utf-8"))
                if rec.get("type") == kind and isinstance(rec.get(field), str) and rec[field].strip():
                    return rec[field][:200]
            except Exception:
                pass
            i = data.rfind(needle, 0, start)
    return ""


def agent_meta(p: dict) -> dict:
    """A subagent's task description (the Agent tool's "description") and the id of the Agent
    call that started it, from the small <session>/subagents/agent-<id>.meta.json beside the
    transcript; {} until Claude writes it."""
    path, sid, aid = p.get("transcript_path"), p.get("session_id"), p.get("agent_id")
    if not (isinstance(path, str) and path and isinstance(sid, str) and isinstance(aid, str)
            and sid and aid and all(c.isalnum() or c in "-_" for c in sid + aid)):
        return {}
    folder = os.path.dirname(path)
    if os.path.basename(folder) != "subagents":     # the lead's transcript, not the agent's own
        folder = os.path.join(folder, sid, "subagents")
    meta = os.path.join(folder, f"agent-{aid}.meta.json")
    with open(meta, encoding="utf-8") as f:
        m = json.loads(f.read(65536))
    out = {}
    if isinstance(m.get("description"), str):
        out["agent_description"] = m["description"][:200]
    if isinstance(m.get("toolUseId"), str):
        out["agent_tool_use_id"] = m["toolUseId"][:100]
    return out


def read_stdin() -> bytes:
    """Read all of stdin. In the windowed exe sys.stdin can be None, so fall back to the
    raw Windows handle Claude Code piped in."""
    if sys.stdin is not None:
        return sys.stdin.buffer.read()
    if os.name != "nt":
        return b""
    import ctypes
    import msvcrt
    get = ctypes.windll.kernel32.GetStdHandle
    get.restype = ctypes.c_void_p
    handle = get(-10)  # STD_INPUT_HANDLE
    if not handle or handle == ctypes.c_void_p(-1).value:
        return b""
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    chunks = []
    while True:
        b = os.read(fd, 65536)
        if not b:
            break
        chunks.append(b)
    return b"".join(chunks)


def main() -> None:
    ts = time.time()  # when the event happened; lets the server ignore late async posts
    raw = read_stdin()
    p = json.loads(raw.decode("utf-8", "replace") or "{}")
    if not isinstance(p, dict):
        return
    ti = p.get("tool_input")
    if isinstance(ti, dict):
        p["tool_input"] = {k: str(v)[:200] for k, v in ti.items() if k in KEEP_INPUT}
    p.pop("tool_response", None)
    for k in ("prompt", "last_assistant_message", "message", "error"):
        if isinstance(p.get(k), str):
            p[k] = p[k][:2000]
    p["ts"] = ts
    try:
        if p.get("agent_id"):
            p.update(agent_meta(p))
        else:
            p["session_title"] = session_title(p.get("transcript_path"))
    except Exception:
        pass
    port = os.environ.get("CLAUDE_OFFICE_PORT") or "8777"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/hook", data=json.dumps(p).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # Short timeout: Windows takes ~2s to refuse a connection to a closed port.
    opener.open(req, timeout=0.5).read()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
