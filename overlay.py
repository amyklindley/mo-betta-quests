#!/usr/bin/env python3
"""Mo Betta Quests: tray app + always-on-top quest overlay for Monsters & Memories.

Runs in the system tray. The overlay window lists the active character's open
tasks with a checkbox per task; closing the window only hides it.

Ways to control it:
  * tray icon menu (right-click)
  * hotkey Ctrl+Shift+Q toggles the overlay
  * "/mobetta <command>" typed on its own line in the game's /note window (/mbq, /mnmquest also work)
  * running the exe again while it is open:  MoBettaQuests.exe open|hide|toggle|reload|quit

  python overlay.py            run
  python overlay.py Denvan     pin to one character instead of auto-detect
  python overlay.py --selftest open, then close itself after 3 s (for testing)
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
import traceback
import webbrowser
import winreg
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont

import mnm_quests as mq

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:  # running from source without the tray libs: overlay still works
    pystray = None

APP_NAME = "MoBettaQuests"
POS_FILE = mq.HERE / "overlay_pos.json"  # next to the exe when packaged, next to the script otherwise
# A second launch drops its command here for the running instance. Shared per user, not per
# copy of the exe, so a click on any copy reaches whichever copy is running.
CMD_FILE = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "MoBettaQuests.command"
LOG_FILE = mq.HERE / "MoBettaQuests.log"
MUTEX_NAME = "Local\\MoBettaQuests-single-instance"
BG, FG, DIM, ACCENT = "#14161c", "#e6e1d6", "#8d8a80", "#d9a441"
CARD = "#1a1d25"
WRAP = 400
TICK_MS = 1000  # command file / queue poll
SCAN_TICKS = 5  # journal scan every N ticks
HOTKEY_ID = 1
WM_HOTKEY = 0x0312
MOD_CONTROL, MOD_SHIFT, VK_Q = 0x0002, 0x0004, 0x51
WINDOW_CMDS = ("open", "show", "hide", "close", "toggle", "reload", "refresh", "collapse", "expand",
               "char", "auto", "startup", "quit", "exit", "help")


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- single instance

def already_running() -> bool:
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW(None, False, MUTEX_NAME)
    return k32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def send_to_running(cmd: str) -> None:
    try:
        CMD_FILE.write_text(cmd + "\n", "utf-8")
        log(f"already running; sent '{cmd}' to the running copy")
    except OSError as e:
        log(f"already running but could not hand over '{cmd}': {e}")


# ---------------------------------------------------------------- start with Windows

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_startup(on: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- hotkey thread

def hotkey_loop(q: "queue.Queue[tuple[str, str | None]]") -> None:
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_Q):
        log("hotkey Ctrl+Shift+Q unavailable (another app owns it)")
        return
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            q.put(("toggle", None))


# ---------------------------------------------------------------- tray icon

def tray_image() -> "Image.Image":
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(20, 22, 28, 255), outline=(217, 164, 65, 255), width=3)
    d.line((16, 34, 28, 46, 48, 20), fill=(217, 164, 65, 255), width=7, joint="curve")
    return img


# ---------------------------------------------------------------- app

class App:
    def __init__(self, force_char: str | None, selftest: bool) -> None:
        self.force_char = force_char
        self.collapsed = False
        self.visible = True
        self.show_help = False
        self.expanded: dict[str, bool] = {}
        self.show_archive: dict[str, bool] = {}
        self.show_ctx: set[str] = set()  # task ids whose surrounding dialogue is expanded
        self.open_cards: set[str] = set()  # quest cards showing their details
        self.view_char: str | None = None  # character tab chosen by hand (None = follow the game)
        self._cards: dict[str, list[mq.Card]] = {}
        self.last_active: str | None = None
        self.last_snapshot: tuple | None = None
        self.q: "queue.Queue[tuple[str, str | None]]" = queue.Queue()
        self.ticks = 0
        self.tray = None
        self._data: dict = {}
        self._active: str | None = None

        self.root = tk.Tk()
        self.root.title("Mo Betta Quests")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)
        self.root.configure(bg=BG)
        self.root.geometry(self._load_pos())

        self.bold = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.normal = tkfont.Font(family="Segoe UI", size=9)
        self.small = tkfont.Font(family="Segoe UI", size=8)
        self.struck = tkfont.Font(family="Segoe UI", size=9, overstrike=True)

        header = tk.Frame(self.root, bg="#0e1015", cursor="fleur")
        header.pack(fill="x")
        self.title = tk.Label(header, text="Mo Betta Quests", bg="#0e1015", fg=ACCENT, font=self.bold, anchor="w", padx=8)
        self.title.pack(side="left", fill="x", expand=True)
        for text, cmd in (("refresh", self.refresh), ("–", self.toggle_collapse), ("×", self.hide_window)):
            tk.Button(header, text=text, command=cmd, bg="#0e1015", fg=DIM, activebackground="#22252e",
                      activeforeground=FG, relief="flat", font=self.small, padx=6).pack(side="right")
        for w in (header, self.title):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # Scrollable body: a frame inside a canvas, height capped so a long list never runs off screen.
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0, bd=0, width=WRAP + 90)
        self.scroll = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview, width=8)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=BG, padx=8, pady=6)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.body_id, width=e.width))
        self.root.bind_all("<MouseWheel>", self._wheel)
        self._last_sig: tuple | None = None

        threading.Thread(target=hotkey_loop, args=(self.q,), daemon=True).start()
        self._start_tray()
        self.refresh()
        self.root.after(TICK_MS, self._tick)
        if selftest:
            self.root.after(3000, self.quit)
        log("started")
        self.root.mainloop()

    # ---------------------------------------------------------------- tray

    def _start_tray(self) -> None:
        if pystray is None:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Show / hide overlay", lambda: self.q.put(("toggle", None)), default=True),
            pystray.MenuItem("Reload quests", lambda: self.q.put(("reload", None))),
            pystray.MenuItem("Start with Windows", lambda: self.q.put(("startup", "toggle")),
                             checked=lambda item: startup_enabled()),
            pystray.MenuItem("Open log", lambda: self.q.put(("log", None))),
            pystray.MenuItem("Quit", lambda: self.q.put(("quit", None))),
        )
        self.tray = pystray.Icon(APP_NAME, tray_image(), "Mo Betta Quests  (Ctrl+Shift+Q)", menu)
        self.tray.run_detached()

    # ---------------------------------------------------------------- commands

    def handle(self, verb: str, arg: str | None) -> None:
        verb = verb.lower()
        log(f"command: {verb} {arg or ''}".rstrip())
        if verb in ("open", "show"):
            self.show_window()
        elif verb in ("hide", "close"):
            self.hide_window()
        elif verb == "toggle":
            self.hide_window() if self.visible else self.show_window()
        elif verb in ("reload", "refresh"):
            self.refresh()
        elif verb == "collapse":
            self.collapsed = False
            self.toggle_collapse()
        elif verb == "expand":
            self.collapsed = True
            self.toggle_collapse()
        elif verb == "char" and arg:
            match = [c for c in self._data if c.lower() == arg.lower()]
            self.view_char = match[0] if match else None
            self._render(self._data, self._active)
        elif verb == "auto":
            self.view_char = None
            self._render(self._data, self._active)
        elif verb == "startup":
            on = (not startup_enabled()) if arg in (None, "toggle") else arg.lower() in ("on", "1", "yes", "true")
            try:
                set_startup(on)
                log(f"start with Windows: {'on' if on else 'off'}")
            except OSError as e:
                log(f"could not change startup setting: {e}")
            if self.tray:
                self.tray.update_menu()
        elif verb == "help":
            self.show_help = True
            self.refresh()
        elif verb == "log":
            try:
                os.startfile(LOG_FILE)
            except OSError:
                pass
        elif verb in ("quit", "exit"):
            self.quit()
        else:
            log(f"unknown command: {verb}")

    def _tick(self) -> None:
        # 1. commands from a second launch
        try:
            if CMD_FILE.exists():
                text = CMD_FILE.read_text("utf-8")
                CMD_FILE.unlink()
                for line in text.splitlines():
                    parts = line.split(None, 1)
                    if parts:
                        self.q.put((parts[0], parts[1] if len(parts) > 1 else None))
        except OSError:
            pass
        # 2. commands from hotkey / tray
        while True:
            try:
                verb, arg = self.q.get_nowait()
            except queue.Empty:
                break
            try:
                self.handle(verb, arg)
            except Exception:
                log("error handling command:\n" + traceback.format_exc())
        # 3. journal / notes changes
        self.ticks += 1
        if self.ticks % SCAN_TICKS == 0:
            try:
                cur = mq.snapshot()
            except OSError:
                cur = None
            if cur != self.last_snapshot:
                self.refresh()
        self.root.after(TICK_MS, self._tick)

    # ---------------------------------------------------------------- data

    def refresh(self) -> None:
        try:
            state = mq.load_state()
            app_cmds = mq.apply_note_corrections(state)
            if app_cmds:
                self.show_help = False  # help text goes away on the next command
            data = mq.parse_all(state)
            active = self.force_char or mq.active_character()
            if active not in data:
                match = [c for c in data if active and c.lower() == active.lower()]
                active = match[0] if match else next(iter(data), None)
            mq.MD_FILE.write_text(mq.render_md(data, show_all=True), "utf-8")
            mq.write_unmatched(data)
            for verb, arg in app_cmds:
                if verb == "help":
                    self.show_help = True
            mq.write_notes(mq.render_notes_block(data, active, help_text=self.show_help))
            self._data, self._active = data, active
            self._render(data, active)
            for verb, arg in app_cmds:
                if verb != "help":
                    self.q.put((verb, arg))
        except mq.GameDataNotFoundError as e:
            # Fresh install / game not launched yet: show the empty state instead
            # of dying (SystemExit used to escape the generic handler below).
            log(f"no game data yet ({e}); showing empty state")
            self._data, self._active = {}, None
            self._render({}, None)
        except Exception:
            log("error during refresh:\n" + traceback.format_exc())
        try:
            self.last_snapshot = mq.snapshot()
        except OSError:
            self.last_snapshot = None

    def _mark(self, verb: str, tid: str) -> None:
        state = mq.load_state()
        mq._apply(state, verb, tid)
        mq.save_state(state)
        self.refresh()

    # ---------------------------------------------------------------- ui

    # ---------------------------------------------------------------- what is drawn

    def _signature(self, data: dict[str, list[mq.Npc]], active: str | None) -> tuple:
        """Everything that affects what is drawn. Same signature = no rebuild, no flicker."""
        view = self.view_char or active
        cards = self._cards.get(view, []) if view else []
        return (
            view, active, self.collapsed, tuple(sorted(self.open_cards)), self.show_archive.get(view or "", False),
            tuple(sorted(self.show_ctx)),
            tuple((c, sum(len(mq.open_tasks(n)) for n in npcs)) for c, npcs in data.items()),
            tuple((k.key, k.title, k.subtitle, k.now, k.say, tuple((i.name, i.counter, i.done) for i, _, _ in k.items),
                   tuple((t.id, t.status, t.text) for t in k.tasks), tuple(k.given), tuple(k.rewards)) for k in cards),
        )

    def _render(self, data: dict[str, list[mq.Npc]], active: str | None) -> None:
        if active is not None and active != self.last_active:
            self.last_active = active
            self.view_char = None  # follow the game when it switches character
        self._cards = {c: mq.build_cards(npcs) for c, npcs in data.items()}
        sig = self._signature(data, active)
        if sig == self._last_sig:
            return
        self._last_sig = sig
        scroll_pos = self.canvas.yview()[0]
        for w in self.body.winfo_children():
            w.destroy()
        view = self.view_char if self.view_char in data else active
        if not view or view not in data:
            tk.Label(self.body, text="no characters found - play a bit first", bg=BG, fg=DIM,
                     font=self.normal).pack()
            self._fit(scroll_pos)
            return
        n_quests = sum(1 for k in self._cards[view] if k.open)
        self.title.config(text=f"Mo Betta Quests  ·  {view}  ·  {n_quests} quest{'s' if n_quests != 1 else ''}")
        if self.collapsed:
            return
        self._char_tabs(data, active, view)
        self._build_cards(view)
        self._fit(scroll_pos)

    def _fit(self, scroll_pos: float = 0.0) -> None:
        """Size the canvas to the content, capped at 75% of the screen; show the scrollbar only when needed."""
        self.body.update_idletasks()
        req_h, req_w = self.body.winfo_reqheight(), self.body.winfo_reqwidth()
        max_h = int(self.root.winfo_screenheight() * 0.75)
        self.canvas.configure(height=min(req_h, max_h), scrollregion=(0, 0, req_w, req_h))
        if req_h > max_h:
            self.scroll.pack(side="right", fill="y")
        else:
            self.scroll.pack_forget()
        self.canvas.yview_moveto(scroll_pos)

    def _wheel(self, e: tk.Event) -> None:
        if self.scroll.winfo_ismapped():
            self.canvas.yview_scroll(int(-e.delta / 120), "units")

    # ---------------------------------------------------------------- character tabs

    def _char_tabs(self, data: dict[str, list[mq.Npc]], active: str | None, view: str) -> None:
        chars = sorted(data, key=lambda c: (c != active, c))
        if len(chars) <= 1:
            return
        bar = tk.Frame(self.body, bg=BG)
        bar.pack(fill="x", pady=(0, 6))
        row = None
        for i, c in enumerate(chars):
            if i % 4 == 0:
                row = tk.Frame(bar, bg=BG)
                row.pack(fill="x", pady=(0, 3))
            n_open = sum(1 for k in self._cards[c] if k.open)
            is_view = c == view
            text = f"{'● ' if c == active else ''}{c}  {n_open}"
            chip = tk.Label(row, text=text, bg="#2a2e3a" if is_view else "#1c1f27", fg=ACCENT if is_view else DIM,
                            font=self.small, padx=8, pady=3, cursor="hand2")
            chip.pack(side="left", padx=(0, 4))
            chip.bind("<Button-1>", lambda e, ch=c: self._view(ch))

    def _view(self, char: str) -> None:
        self.view_char = None if char == self.last_active else char
        self._render(self._data, self._active)

    # ---------------------------------------------------------------- quest cards

    def _build_cards(self, view: str) -> None:
        cards = self._cards[view]
        shown = [k for k in cards if k.open]
        if not shown:
            tk.Label(self.body, text="nothing open", bg=BG, fg=DIM, font=self.normal, padx=6).pack(anchor="w")
        for k in shown:
            self._card(k)
        archive = [t for k in cards for t in k.tasks if t.status != "open"]
        if archive:
            arch_open = self.show_archive.get(view, False)
            lbl = tk.Label(self.body, text=f"{'▾' if arch_open else '▸'} done & hidden ({len(archive)})",
                           bg=BG, fg=DIM, font=self.small, anchor="w", padx=6, cursor="hand2")
            lbl.pack(fill="x", pady=(4, 0))
            lbl.bind("<Button-1>", lambda e, v=view: self._toggle_archive(v))
            if arch_open:
                for t in sorted(archive, key=lambda t: t.when, reverse=True):
                    self._archive_row(t)

    def _card(self, k: mq.Card) -> None:
        f = tk.Frame(self.body, bg=CARD, highlightbackground="#2a2e3a", highlightthickness=1)
        f.pack(fill="x", pady=(0, 6))
        head = tk.Frame(f, bg=CARD)
        head.pack(fill="x")
        is_open = k.key in self.open_cards
        title = tk.Label(head, text=f"{'▾' if is_open else '▸'} {k.title}", bg=CARD, fg=ACCENT, font=self.bold,
                         anchor="w", padx=8, pady=4, cursor="hand2", wraplength=WRAP - 110, justify="left")
        title.pack(side="left", fill="x", expand=True)
        title.bind("<Button-1>", lambda e, key=k.key: self._toggle_card(key))
        for text, verb in (("hide", "hide"), ("✔ done", "done")):
            tk.Button(head, text=text, command=lambda v=verb, key=k.key: self._card_mark(key, v), bg=CARD,
                      fg=ACCENT if verb == "done" else DIM, activebackground="#2a2e3a", activeforeground=FG,
                      relief="flat", font=self.small, padx=6).pack(side="right", padx=(0, 4))
        if k.subtitle or k.by_name:
            sub = k.subtitle + ("   (wiki match by NPC name)" if k.by_name else "")
            tk.Label(f, text=sub, bg=CARD, fg=DIM, font=self.small, anchor="w", padx=10).pack(fill="x")
        if k.now:
            tk.Label(f, text=k.now, bg=CARD, fg=FG, font=self.normal, anchor="w", padx=10, pady=2,
                     wraplength=WRAP - 20, justify="left").pack(fill="x")
        for it, tid, idx in k.items:
            row = tk.Frame(f, bg=CARD)
            row.pack(fill="x", padx=(22, 8))
            g = tk.Label(row, text="✔" if it.done else "○", bg=CARD, fg=ACCENT if it.done else DIM, font=self.small,
                         width=2, cursor="hand2")
            g.pack(side="left")
            g.bind("<Button-1>", lambda e, t=tid, i=idx, on=not it.manual: self._got(t, i, on))
            tk.Label(row, text=it.name, bg=CARD, fg=DIM if it.done else FG, font=self.small, anchor="w",
                     wraplength=WRAP - 90, justify="left").pack(side="left", fill="x", expand=True)
            tk.Label(row, text=it.counter, bg=CARD, fg=ACCENT if it.done else FG, font=self.small).pack(side="right")
        if k.say:
            tk.Label(f, text=f'say: "{k.say}"', bg=CARD, fg="#9fd3a8", font=self.small, anchor="w", padx=10,
                     wraplength=WRAP - 20, justify="left").pack(fill="x", pady=(2, 0))
        if is_open:
            self._card_details(f, k)
        tk.Frame(f, bg=CARD, height=4).pack()

    def _card_details(self, f: tk.Frame, k: mq.Card) -> None:
        """Behind the fold: the NPC's own words with per-task controls, reward, hand-outs, wiki link."""
        tk.Frame(f, bg="#2a2e3a", height=1).pack(fill="x", padx=8, pady=(4, 4))
        for t in k.tasks:
            if t.status in ("open", "done"):
                self._task_row(f, t)
        meta: list[str] = []
        if k.rewards:
            meta.append("reward: " + ", ".join(k.rewards))
        if k.given:
            meta.append("gave you: " + ", ".join(k.given[-4:]))
        if len(k.npcs) > 1:
            meta.append("NPCs: " + ", ".join(n.name for n in k.npcs))
        for m in meta:
            tk.Label(f, text=m, bg=CARD, fg=DIM, font=self.small, anchor="w", padx=10, wraplength=WRAP - 20,
                     justify="left").pack(fill="x")
        if k.url:
            link = tk.Label(f, text="open wiki page", bg=CARD, fg="#7fb3ff", font=self.small, anchor="w", padx=10,
                            cursor="hand2")
            link.pack(fill="x", pady=(2, 2))
            link.bind("<Button-1>", lambda e, u=k.url: webbrowser.open(u))

    def _task_row(self, parent: tk.Frame, t: mq.Task) -> None:
        done = t.status == "done"
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=(6, 4))
        var = tk.BooleanVar(value=done)
        tk.Checkbutton(row, variable=var, bg=CARD, fg=ACCENT, activebackground=CARD, activeforeground=ACCENT,
                       selectcolor="#2a2e3a",
                       command=lambda tid=t.id, v=var: self._mark("done" if v.get() else "undo", tid)).pack(
            side="left", anchor="n")
        lbl = tk.Label(row, text=t.text, bg=CARD, fg=DIM if done else FG, font=self.struck if done else self.small,
                       wraplength=WRAP - 80, justify="left", anchor="w", cursor="hand2" if t.context else "")
        lbl.pack(side="left", fill="x", expand=True)
        tk.Button(row, text="hide", command=lambda tid=t.id: self._mark("hide", tid), bg=CARD, fg=DIM,
                  activebackground="#2a2e3a", activeforeground=FG, relief="flat", font=self.small).pack(
            side="right", anchor="n")
        if t.context:
            lbl.bind("<Button-1>", lambda e, tid=t.id: self._toggle_ctx(tid))
            if t.id in self.show_ctx:
                tk.Label(parent, text=t.context, bg="#12141a", fg=DIM, font=self.small, wraplength=WRAP - 40,
                         justify="left", anchor="w", padx=8, pady=4).pack(fill="x", padx=(30, 8), pady=(0, 4))

    def _archive_row(self, t: mq.Task) -> None:
        tag = {"done": "done", "hidden": "hidden", "likely-done": "auto"}.get(t.status, t.status)
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", padx=(12, 0))
        tk.Label(row, text=f"[{tag}] {t.npc}: {t.text}", bg=BG, fg=DIM, font=self.small, wraplength=WRAP - 20,
                 justify="left", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(row, text="undo", command=lambda tid=t.id: self._mark("undo", tid), bg=BG, fg=ACCENT,
                  activebackground="#22252e", activeforeground=FG, relief="flat", font=self.small).pack(
            side="right", anchor="n")

    # ---------------------------------------------------------------- card actions

    def _toggle_card(self, key: str) -> None:
        if key in self.open_cards:
            self.open_cards.discard(key)
        else:
            self.open_cards.add(key)
        self._render(self._data, self._active)

    def _card_mark(self, key: str, verb: str) -> None:
        """✔ done / hide on a card applies to every open task in it."""
        view = self.view_char if self.view_char in self._cards else self._active
        card = next((k for k in self._cards.get(view, []) if k.key == key), None)
        if not card:
            return
        state = mq.load_state()
        for t in card.open_tasks:
            mq._apply(state, verb, t.id)
        mq.save_state(state)
        self.open_cards.discard(key)
        self.refresh()

    def _got(self, tid: str, n: int, on: bool) -> None:
        state = mq.load_state()
        mq.set_got(state, tid, n, on)
        mq.save_state(state)
        self.refresh()

    def _toggle_ctx(self, tid: str) -> None:
        if tid in self.show_ctx:
            self.show_ctx.discard(tid)
        else:
            self.show_ctx.add(tid)
        self._render(self._data, self._active)

    def _toggle_archive(self, char: str) -> None:
        self.show_archive[char] = not self.show_archive.get(char, False)
        self._render(self._data, self._active)

    def toggle_collapse(self) -> None:
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.canvas.pack_forget()
            self.scroll.pack_forget()
        else:
            self.canvas.pack(side="left", fill="both", expand=True)
        self._render(self._data, self._active)

    # ---------------------------------------------------------------- window

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.visible = True

    def hide_window(self) -> None:
        self._save_pos()
        self.root.withdraw()
        self.visible = False
        if pystray is None:  # no tray to bring it back from: closing means quitting
            self.quit()

    def quit(self) -> None:
        self._save_pos()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        log("quit")
        self.root.destroy()

    def _drag_start(self, e: tk.Event) -> None:
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag_move(self, e: tk.Event) -> None:
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _load_pos(self) -> str:
        try:
            p = json.loads(POS_FILE.read_text("utf-8"))
            return f"+{p['x']}+{p['y']}"
        except (OSError, ValueError, KeyError):
            return "+40+40"

    def _save_pos(self) -> None:
        try:
            POS_FILE.write_text(json.dumps({"x": self.root.winfo_x(), "y": self.root.winfo_y()}), "utf-8")
        except OSError:
            pass


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    selftest = "--selftest" in sys.argv
    if not selftest and already_running():
        # Second launch: hand the command to the running instance and leave.
        send_to_running(" ".join(args) if args and args[0].lower() in WINDOW_CMDS else "open")
        return
    if args and args[0].lower() in WINDOW_CMDS:
        # First launch given a window command: just start normally.
        args = args[1:]
    App(args[0] if args else None, selftest)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("fatal:\n" + traceback.format_exc())
        raise
