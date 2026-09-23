"""Shared fixtures: a fake Monsters & Memories game tree, fully offline.

Module-level globals in mnm_quests (GAME_DIR, SERVER, NOTES_FILE, ...) are read
at call time, so monkeypatching them after import is enough to redirect every
read/write into a per-test tmp dir.
"""
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import mnm_quests as mq

ROOT = Path(__file__).resolve().parent.parent


def journal_line(npc: str, when: datetime, text: str) -> str:
    """One line as the game writes it: '<timestamp>: <NPC> <text>'."""
    return f"{when:%Y-%m-%d %H:%M:%S}: {npc} {text}"


def write_journal(char_dir: Path, npc: str, lines: list[str], extra: str = "") -> Path:
    f = char_dir / "journal" / npc
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines) + extra + "\n", encoding="utf-8")
    return f


def write_ledger(char_dir: Path, entries: list[dict]) -> Path:
    """entries: dicts of act/when/qty/name/corpse/zone -> Ledger/0001.json."""
    ledger = char_dir / "Ledger"
    ledger.mkdir(parents=True, exist_ok=True)
    rows = []
    for ev in entries:
        detail = {"d01": str(ev.get("qty", 1))}
        if "name" in ev:
            detail["d04"] = ev["name"]
        if ev.get("corpse"):
            detail["d02"] = base64.b64encode(ev["corpse"].encode()).decode()
        row = {"f01": ev["act"], "f03": json.dumps(detail), "f04": ev["when"].isoformat()}
        if ev.get("zone"):
            row["f05"] = "zone_" + base64.b64encode(ev["zone"].encode()).decode()
        rows.append(row)
    f = ledger / "0001.json"
    f.write_text(json.dumps({"c01": rows}), encoding="utf-8")
    return f


def make_char(root: Path, server: str, char: str) -> Path:
    d = root / server / char
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def game(tmp_path, monkeypatch):
    """Fake game root; all module-level paths redirected into it."""
    root = tmp_path / "game"
    (root / "beta1").mkdir(parents=True)
    monkeypatch.setattr(mq, "GAME_DIR", root)
    monkeypatch.setattr(mq, "SERVER", "beta1")
    monkeypatch.setattr(mq, "NOTES_FILE", root / "notes.txt")
    monkeypatch.setattr(mq, "STATE_FILE", root / "state.json")
    monkeypatch.setattr(mq, "MD_FILE", root / "quests.md")
    monkeypatch.setattr(mq, "UNMATCHED_FILE", root / "unmatched.txt")
    return root


@pytest.fixture
def now():
    return datetime.now()


@pytest.fixture
def soon(now):
    """Reference timestamps a few hours ago (inside the 7-day unmatched window)."""
    return now - timedelta(hours=3)