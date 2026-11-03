r"""UsageWidget.exe: a little always-on-top window with today's Claude tokens and cost and your Cursor spend.

A separate program: it needs neither office open and installs no hooks. Built by scripts/build.bat,
or run unbuilt with `py src/usage_widget.py`. Drag it anywhere; right-click for its menu.

Claude: every transcript under ~/.claude/projects (or CLAUDE_CONFIG_DIR) touched today, counted by the
office's own Usage code, so the same prices and the same day (Eastern time). Local file reads only.

Cursor: the office's own CursorCost code and its saved setting (cursor-cost.json), so it has the same rules:
off until you turn it on (the right-click menu here, or Settings in the Cursor office), the only internet use
here, your own spend only, and the login read fresh and never saved or logged.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import server

CLAUDE_SECONDS = 15    # how often the transcripts are looked at
DRAW_MS = 2000         # how often the window redraws what the background threads found
ONE_COPY_PORT = 8779   # held while the widget runs, so a second copy just exits
BG, FG, DIM, LINE = "#1f1f23", "#f4f5f7", "#9a9ca5", "#3a3a42"
CLAUDE_COLOR, CURSOR_COLOR = "#d97757", "#8f96a3"


class AllClaude(server.Usage):
    """The office's Usage, but reading every transcript touched today instead of waiting for hooks."""

    def scan_all(self) -> None:
        root = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "projects")
        now = time.time()
        midnight = now - (now + server.eastern_offset(now) * 3600) % 86400
        for folder, _, names in os.walk(root):
            for name in names:
                path = os.path.join(folder, name)
                try:
                    if name.endswith(".jsonl") and os.path.getmtime(path) >= midnight:
                        with self.lock:
                            self._roll()
                            self._read(path)
                except OSError:
                    pass


def short_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)


def claude_lines(usage: dict | None) -> tuple[str, str]:
    """(cost, tokens) for the window. Input counts cache writes and reads, as the office's meter does."""
    if usage is None:
        return "…", "counting today's transcripts"
    models = usage["models"]
    cost = sum(m["cost"] for m in models)
    sent = sum(m["input"] + m["cache_write"] + m["cache_read"] for m in models)
    got = sum(m["output"] for m in models)
    more = "" if all(m["priced"] for m in models) else "+"     # a model with no price still counts its tokens
    return f"${cost:,.2f}{more}", f"{short_tokens(sent)} in · {short_tokens(got)} out"


def reset_day(resets: str) -> str:
    try:
        d = datetime.fromisoformat(resets.replace("Z", "+00:00"))
        return f"resets {d:%b} {d.day}"
    except ValueError:
        return ""


def cursor_lines(cost: dict | None) -> tuple[str, str, str, float]:
    """(when, amount, detail, share of the limit used) for the window, from CursorCost.public()."""
    if cost is None:
        return "", "off", "right-click to turn on", 0.0
    when = "today" if cost["mode"] == "key" else "this cycle"
    if cost["mode"] == "key" and not cost["email"]:
        return when, "—", "set CURSOR_COST_EMAIL to your Cursor email", 0.0
    amount = f"${cost['cents'] / 100:,.2f}" if cost["checked"] else ("—" if cost["error"] else "…")
    limit = cost.get("limit") or 0
    share = min(1.0, cost["cents"] / limit) if limit else 0.0
    if cost["error"]:
        return when, amount, cost["error"], share
    parts = [f"of ${limit / 100:,.2f}" if limit else "", reset_day(cost.get("resets") or "")]
    return when, amount, " · ".join(p for p in parts if p) or ("checking Cursor" if not cost["checked"] else ""), share


class Widget:
    def __init__(self) -> None:
        self.claude: dict | None = None    # written by the background thread, read by the window
        self.settings = self._load()
        self.root = root = tk.Tk()
        root.title("Usage Widget")
        root.overrideredirect(True)        # no title bar: drag it by anywhere, close with the x or the menu
        root.configure(bg=LINE)
        self.on_top = tk.BooleanVar(value=self.settings.get("top", True))
        root.attributes("-topmost", self.on_top.get())

        self.body = body = tk.Frame(root, bg=BG, padx=10, pady=7)
        body.pack(padx=1, pady=1)
        body.columnconfigure(1, weight=1, minsize=70)
        self.claude_amount, self.claude_detail = self._row(0, "Claude", CLAUDE_COLOR, "today")[1:]
        tk.Frame(body, bg=LINE, height=1).grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        self.cursor_when, self.cursor_amount, self.cursor_detail = self._row(3, "Cursor", CURSOR_COLOR, "")
        self.bar = tk.Canvas(body, height=3, bg=LINE, highlightthickness=0)
        self.bar_fill = self.bar.create_rectangle(0, 0, 0, 3, fill=CURSOR_COLOR, width=0)

        close = tk.Label(body, text="×", bg=BG, fg=DIM, font=("Segoe UI", 9), padx=2, cursor="hand2")
        close.grid(row=0, column=3, sticky="ne", padx=(6, 0))
        close.bind("<Button-1>", lambda _e: root.destroy())

        self.login = tk.BooleanVar(value=server.CURSOR_COST.login or bool(server.CURSOR_COST.key))
        self.menu = menu = tk.Menu(root, tearoff=0)
        menu.add_checkbutton(label="Always on top", variable=self.on_top, command=self._set_top)
        menu.add_checkbutton(label="Show my Cursor cost", variable=self.login, command=self._set_login,
                             state="disabled" if server.CURSOR_COST.key else "normal")   # a key can't be turned off here
        menu.add_command(label="Check Cursor now", command=server.CURSOR_COST.wake.set)
        menu.add_separator()
        menu.add_command(label="Exit", command=root.destroy)

        self._bind_all(root, close)
        self._draw()
        self._place()
        threading.Thread(target=self._watch_claude, daemon=True).start()

    def _row(self, row: int, name: str, color: str, when: str) -> tuple[tk.Label, tk.Label, tk.Label]:
        head = tk.Frame(self.body, bg=BG)
        head.grid(row=row, column=0, sticky="w")
        tk.Label(head, text="●", bg=BG, fg=color, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(head, text=name, bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(3, 4))
        when_label = tk.Label(head, text=when, bg=BG, fg=DIM, font=("Segoe UI", 8))
        when_label.pack(side="left")
        amount = tk.Label(self.body, bg=BG, fg=FG, font=("Segoe UI", 11, "bold"))
        amount.grid(row=row, column=1, sticky="e", padx=(14, 0))
        detail = tk.Label(self.body, bg=BG, fg=DIM, font=("Segoe UI", 8), wraplength=205, justify="left")
        detail.grid(row=row + 1, column=0, columnspan=3, sticky="w")
        return when_label, amount, detail

    def _bind_all(self, widget: tk.Misc, close: tk.Label) -> None:
        if widget is not close:
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", lambda _e: self._save())
            widget.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        for child in widget.winfo_children():
            if not isinstance(child, tk.Menu):
                self._bind_all(child, close)

    def _drag_start(self, e: tk.Event) -> None:
        self.grab = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag(self, e: tk.Event) -> None:
        self.root.geometry(f"+{e.x_root - self.grab[0]}+{e.y_root - self.grab[1]}")

    def _place(self) -> None:
        """Where you last left it, unless that's off every screen now; first time, the bottom right."""
        root = self.root
        root.update_idletasks()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        left, top, width, height = 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
        if os.name == "nt":
            import ctypes
            left, top, width, height = (ctypes.windll.user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))
        x, y = self.settings.get("x"), self.settings.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not (left <= x <= left + width - w and top <= y <= top + height - h):
            x, y = root.winfo_screenwidth() - w - 24, root.winfo_screenheight() - h - 72
        root.geometry(f"+{x}+{y}")

    def _path(self) -> str:
        return os.path.join(server.data_dir(), "usage-widget.json")

    def _load(self) -> dict:
        try:
            with open(self._path(), encoding="utf-8") as f:
                out = json.load(f)
            return out if isinstance(out, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        try:
            os.makedirs(server.data_dir(), exist_ok=True)
            with open(self._path(), "w", encoding="utf-8") as f:
                json.dump({"x": self.root.winfo_x(), "y": self.root.winfo_y(), "top": self.on_top.get()}, f)
        except OSError:
            pass

    def _set_top(self) -> None:
        self.root.attributes("-topmost", self.on_top.get())
        self._save()

    def _set_login(self) -> None:
        if self.login.get() and not messagebox.askyesno("Show my Cursor cost", (
                "This reads your login from the Cursor app on this PC and uses it to ask Cursor for your own spend, "
                "through private Cursor calls that can change without notice. The login is never saved or logged and "
                "goes only to Cursor.\n\nOn a company account, check that your company allows it.\n\nTurn it on?"),
                parent=self.root):
            self.login.set(False)
            return
        try:
            server.CURSOR_COST.set_login(self.login.get())
        except OSError:
            pass
        self._draw()

    def _watch_claude(self) -> None:
        usage = AllClaude()
        while True:
            try:
                usage.scan_all()
                self.claude = usage.public()
            except Exception:      # a transcript in a shape we don't expect: try again next time
                pass
            time.sleep(CLAUDE_SECONDS)

    def _draw(self) -> None:
        amount, detail = claude_lines(self.claude)
        self.claude_amount.config(text=amount)
        self.claude_detail.config(text=detail)
        when, amount, detail, share = cursor_lines(server.CURSOR_COST.public())
        self.cursor_when.config(text=when)
        self.cursor_amount.config(text=amount)
        self.cursor_detail.config(text=detail)
        if share:
            self.bar.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(3, 1))
            self.bar.coords(self.bar_fill, 0, 0, self.bar.winfo_width() * share, 3)
        else:
            self.bar.grid_remove()
        self.root.after(DRAW_MS, self._draw)


def main() -> None:
    holder = socket.socket()
    try:
        holder.bind(("127.0.0.1", ONE_COPY_PORT))
    except OSError:
        sys.exit(0)        # already running
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)     # sharp text on a scaled display
        except (AttributeError, OSError):
            pass
    server.CURSOR_COST.start()
    Widget().root.mainloop()


if __name__ == "__main__":
    main()
