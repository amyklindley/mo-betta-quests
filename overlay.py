#!/usr/bin/env python3
"""Always-on-top quest overlay for Monsters & Memories.

Shows the active character's open tasks with a checkbox per task. Ticking a
box marks it done, the small x hides it forever. The overlay also does the
watcher's job: it keeps notes.txt (the in-game /note window) up to date, so
you do not need watch-notes.bat while this is running.

  python overlay.py            run
  python overlay.py Denvan     pin to one character instead of auto-detect
  python overlay.py --selftest open, then close itself after 3 s (for testing)
"""
from __future__ import annotations

import json
import sys
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

import mnm_quests as mq

POS_FILE = mq.HERE / "overlay_pos.json"  # next to the exe when packaged, next to the script otherwise
BG, FG, DIM, ACCENT = "#14161c", "#e6e1d6", "#8d8a80", "#d9a441"
WRAP = 400
POLL_MS = 5000


class Overlay:
    def __init__(self, force_char: str | None, selftest: bool) -> None:
        self.force_char = force_char
        self.collapsed = False
        self.expanded: dict[str, bool] = {}  # per-character section state
        self.show_archive: dict[str, bool] = {}  # per-character "done & hidden" fold
        self.last_active: str | None = None
        self.last_snapshot: tuple | None = None
        self.root = tk.Tk()
        self.root.title("MnM Quests")
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
        self.title = tk.Label(header, text="MnM Quests", bg="#0e1015", fg=ACCENT, font=self.bold, anchor="w", padx=8)
        self.title.pack(side="left", fill="x", expand=True)
        for text, cmd in (("refresh", self.refresh), ("–", self.toggle), ("×", self.quit)):
            tk.Button(header, text=text, command=cmd, bg="#0e1015", fg=DIM, activebackground="#22252e",
                      activeforeground=FG, relief="flat", font=self.small, padx=6).pack(side="right")
        for w in (header, self.title):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        self.body = tk.Frame(self.root, bg=BG, padx=8, pady=6)
        self.body.pack(fill="both", expand=True)

        self.refresh()
        self.root.after(POLL_MS, self._poll)
        if selftest:
            self.root.after(3000, self.quit)
        self.root.mainloop()

    # ---------------------------------------------------------------- data

    def refresh(self) -> None:
        state = mq.load_state()
        mq.apply_note_corrections(state)
        data = mq.parse_all(state)
        active = self.force_char or mq.active_character()
        if active not in data:
            active = next(iter(data), None)
        # Keep the in-game note in sync as well.
        mq.MD_FILE.write_text(mq.render_md(data, show_all=True), "utf-8")
        mq.write_notes(mq.render_notes_block(data, active))
        self._data, self._active = data, active
        self._render(data, active)
        try:
            self.last_snapshot = mq.snapshot()
        except OSError:
            self.last_snapshot = None

    def _poll(self) -> None:
        try:
            cur = mq.snapshot()
        except OSError:
            cur = None
        if cur != self.last_snapshot:
            self.refresh()
        self.root.after(POLL_MS, self._poll)

    def _mark(self, verb: str, tid: str) -> None:
        state = mq.load_state()
        mq._apply(state, verb, tid)
        mq.save_state(state)
        self.refresh()

    # ---------------------------------------------------------------- ui

    def _render(self, data: dict[str, list[mq.Npc]], active: str | None) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        if not active:
            tk.Label(self.body, text="no characters found", bg=BG, fg=DIM, font=self.normal).pack()
            return
        # When the game switches character, open that section and fold the rest.
        if active != self.last_active:
            for c in data:
                self.expanded[c] = c == active
            self.last_active = active
        total = sum(len(mq.open_tasks(n)) for npcs in data.values() for n in npcs)
        self.title.config(text=f"MnM Quests  ·  {total} open")
        if self.collapsed:
            return
        for char in sorted(data, key=lambda c: (c != active, c)):
            npcs = data[char]
            n_open = sum(len(mq.open_tasks(n)) for n in npcs)
            is_open = self.expanded.get(char, False)
            arrow = "▾" if is_open else "▸"
            you = "  (playing)" if char == active else ""
            hdr = tk.Label(self.body, text=f"{arrow} {char}  ·  {n_open} open{you}", bg="#1c1f27",
                           fg=FG if is_open else DIM, font=self.bold, anchor="w", padx=6, pady=3, cursor="hand2")
            hdr.pack(fill="x", pady=(6, 0))
            hdr.bind("<Button-1>", lambda e, c=char: self._toggle_char(c))
            if not is_open:
                continue
            shown = False
            archive: list[mq.Task] = []  # done/hidden/likely-done tasks not in the main list
            for npc in npcs:
                open_ = mq.open_tasks(npc)
                if not open_:
                    # Quest complete (or nothing asked): the group leaves the main list.
                    archive += [t for t in npc.tasks if t.status != "open"]
                    continue
                shown = True
                # Done tasks stay visible, ticked, while the NPC still has open tasks.
                listed = [t for t in npc.tasks if t.status in ("open", "done")]
                archive += [t for t in npc.tasks if t.status in ("hidden", "likely-done")]
                zone = f"  [{npc.zone}]" if npc.zone else ""
                tk.Label(self.body, text=npc.name + zone, bg=BG, fg=ACCENT, font=self.bold, anchor="w",
                         padx=6).pack(fill="x", pady=(4, 0))
                for t in listed:
                    self._task_row(t)
            if not shown:
                tk.Label(self.body, text="nothing open", bg=BG, fg=DIM, font=self.normal, padx=12).pack(anchor="w")
            if archive:
                arch_open = self.show_archive.get(char, False)
                lbl = tk.Label(self.body, text=f"{'▾' if arch_open else '▸'} done & hidden ({len(archive)})",
                               bg=BG, fg=DIM, font=self.small, anchor="w", padx=12, cursor="hand2")
                lbl.pack(fill="x", pady=(4, 0))
                lbl.bind("<Button-1>", lambda e, c=char: self._toggle_archive(c))
                if arch_open:
                    for t in sorted(archive, key=lambda t: t.when, reverse=True):
                        self._archive_row(t)

    def _task_row(self, t: mq.Task) -> None:
        done = t.status == "done"
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", padx=(6, 0))
        var = tk.BooleanVar(value=done)
        tk.Checkbutton(row, variable=var, bg=BG, fg=ACCENT, activebackground=BG, activeforeground=ACCENT,
                       selectcolor="#2a2e3a",
                       command=lambda tid=t.id, v=var: self._mark("done" if v.get() else "undo", tid)).pack(
            side="left", anchor="n")
        tk.Label(row, text=t.text, bg=BG, fg=DIM if done else FG, font=self.struck if done else self.normal,
                 wraplength=WRAP, justify="left", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(row, text="hide", command=lambda tid=t.id: self._mark("hide", tid), bg=BG, fg=DIM,
                  activebackground="#22252e", activeforeground=FG, relief="flat", font=self.small).pack(
            side="right", anchor="n")

    def _archive_row(self, t: mq.Task) -> None:
        tag = {"done": "done", "hidden": "hidden", "likely-done": "auto"}.get(t.status, t.status)
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", padx=(18, 0))
        tk.Label(row, text=f"[{tag}] {t.npc}: {t.text}", bg=BG, fg=DIM, font=self.small, wraplength=WRAP - 20,
                 justify="left", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(row, text="undo", command=lambda tid=t.id: self._mark("undo", tid), bg=BG, fg=ACCENT,
                  activebackground="#22252e", activeforeground=FG, relief="flat", font=self.small).pack(
            side="right", anchor="n")

    def _toggle_archive(self, char: str) -> None:
        self.show_archive[char] = not self.show_archive.get(char, False)
        self._render(self._data, self._active)

    def _toggle_char(self, char: str) -> None:
        self.expanded[char] = not self.expanded.get(char, False)
        self._render(self._data, self._active)

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
        else:
            self.body.pack(fill="both", expand=True)
        self.refresh()

    def quit(self) -> None:
        self._save_pos()
        self.root.destroy()

    # ---------------------------------------------------------------- window position

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


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    Overlay(args[0] if args else None, "--selftest" in sys.argv)
