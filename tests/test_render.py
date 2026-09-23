"""Rendering: markdown export and the in-game /note block."""
from datetime import datetime

import mnm_quests as mq

T0 = datetime(2026, 9, 1, 12, 0, 0)


def _task(tid, text, status="open", items=()):
    t = mq.Task(tid, "Tavi", "Merchant", T0, text, status=status)
    t.items = list(items)
    return t


def _npc(tasks, zone="Night Harbor East", given=()):
    return mq.Npc("Tavi", "Merchant", T0, tasks=tasks, zone=zone, given=list(given))


def test_render_md_open_only():
    data = {"Tavi": [_npc([_task("abc123", "Bring me five bone chips."),
                           _task("def456", "Take the key to the smith.", status="done")])]}
    md = mq.render_md(data)
    assert "## Tavi" in md
    assert "- [ ] `abc123` Bring me five bone chips." in md
    assert "def456" not in md  # done tasks hidden unless show_all


def test_render_md_show_all_marks():
    data = {"Tavi": [_npc([_task("abc123", "A", status="open"),
                           _task("def456", "B", status="done"),
                           _task("789abc", "C", status="hidden"),
                           _task("def123", "D", status="likely-done")])]}
    md = mq.render_md(data, show_all=True)
    assert "- [ ] `abc123` A" in md
    assert "- [x] `def456` B" in md
    assert "- [-] `789abc` C" in md
    assert "- [~] `def123` D" in md


def test_render_md_nothing_open():
    data = {"Tavi": [_npc([_task("abc123", "A", status="done")])]}
    assert "_nothing open_" in mq.render_md(data)


def test_render_md_items_and_given():
    t = _task("abc123", "Bring me five bone chips.", items=[mq.Item("Bone Chip", 5, 3), mq.Item("Rat Tail", 2, 0)])
    npc = _npc([t], given=[(T0, "a small key")])
    md = mq.render_md({"Tavi": [npc]}, show_all=True)
    assert "gave you: a small key" in md
    assert "1. Bone Chip **3/5**" in md
    assert "2. Rat Tail **0/2**" in md


def test_render_md_recent_turn_ins():
    npc = mq.Npc("Tavi", "Merchant", T0, turn_ins=[(T0, "Thank you for your help.")])
    md = mq.render_md({"Tavi": [npc]}, show_all=True)
    assert "Recent turn-ins" in md
    assert "Thank you for your help." in md


def test_render_notes_block_active_and_others():
    t = _task("abc123", "Bring me five bone chips.")
    active_npc = _npc([t])
    other_npc = _npc([_task("def456", "Sweep the hall.", status="open")])
    block = mq.render_notes_block({"Tavi": [active_npc], "Ulric": [other_npc]}, active="Tavi")
    assert "== Tavi (1 open) ==" in block
    assert "abc123" in block
    assert "other chars: Ulric 1" in block
    assert "Sweep the hall." not in block  # collapsed to a count
    assert block.startswith(mq.BLOCK_START) and block.endswith(mq.BLOCK_END)


def test_render_notes_block_help_text():
    block = mq.render_notes_block({}, None, help_text=True)
    assert "/mobetta commands" in block


def test_render_notes_block_given_items():
    npc = _npc([_task("abc123", "A")], given=[(T0, "a key"), (T0, "a pouch")])
    block = mq.render_notes_block({"Tavi": [npc]}, active="Tavi")
    # Card format: title [zone], the "now" line, then the tasks.
    assert "* Merchant [Night Harbor East]" in block
    assert "  now: A" in block
    assert "(abc123)" in block


def test_strip_stamp():
    assert mq._strip_stamp("updated Sep 24 12:00\ncontent") == "content"
    assert mq._strip_stamp("content") == "content"