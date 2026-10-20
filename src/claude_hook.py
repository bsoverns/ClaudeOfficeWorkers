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

KEEP_INPUT = ("command", "file_path", "pattern", "query", "url", "description", "subagent_type")


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
