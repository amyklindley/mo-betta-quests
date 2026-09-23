#!/usr/bin/env python3
"""Monsters & Memories quest tracker.

Reads the game's per-NPC journal files, pulls out the sentences where an NPC
asks you to do something, and writes a compact quest block into the in-game
/note file (notes.txt) below whatever you typed there yourself.

Usage:
  python mnm_quests.py list [CHAR]      print open quests (markdown)
  python mnm_quests.py write [CHAR]     update notes.txt + quests.md (CHAR overrides auto-detect)
  python mnm_quests.py watch [SECONDS]  re-run write whenever the journal changes
  python mnm_quests.py done ID [ID..]   mark a task finished (by its 6-char id)
  python mnm_quests.py undo ID          re-open a task
  python mnm_quests.py hide ID          hide a false positive forever
  python mnm_quests.py all [CHAR]       list everything incl. done/hidden/likely-done
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

GAME_DIR = Path(os.environ.get("USERPROFILE", "")) / "AppData/LocalLow/Niche Worlds Cult/Monsters and Memories"
# When packaged with PyInstaller, keep state next to the .exe, not in the temp unpack dir.
HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
MD_FILE = HERE / "quests.md"
NOTES_FILE = GAME_DIR / "notes.txt"


def _detect_server() -> str:
    """The game keeps one folder per server (beta1, ...). Pick the most recently used one."""
    best, best_t = "beta1", -1.0
    if GAME_DIR.is_dir():
        for d in GAME_DIR.iterdir():
            if d.is_dir() and any((c / "journal").is_dir() for c in d.iterdir() if c.is_dir()):
                t = max((p.stat().st_mtime for p in d.rglob("*") if p.is_file()), default=0.0)
                if t > best_t:
                    best, best_t = d.name, t
    return best


SERVER = _detect_server()

BLOCK_START = "===== MO BETTA QUESTS (auto-generated, edits below are overwritten) ====="
BLOCK_END = "===== END MO BETTA QUESTS ====="
# Markers written by older versions; recognised so an upgrade replaces the old block instead of stacking a new one.
OLD_MARKERS = [("===== QUEST TRACKER (auto-generated, edits below are overwritten) =====", "===== END QUEST TRACKER =====")]

# The vocabulary lives in phrases.py (plain lists, easy to extend). Compiled here.
import phrases as P


def _alt(items: list[str]) -> str:
    return "|".join(f"(?:{p})" for p in items)


NOISE_RE = re.compile(_alt(P.NOISE), re.I)
REQUEST_RE = re.compile(r"\b(?:" + _alt(P.REQUEST) + r")", re.I)
PHRASE_RE = re.compile(r"\b(?:" + _alt(P.PHRASES + P.OBLIGATION) + r")\b", re.I)
IMPERATIVE_RE = re.compile(
    r"^(?:(?:" + _alt(P.LEAD_INS) + r"),?\s+)*(?:please\s+)?(?:"
    + _alt(sorted(P.IMPERATIVE_VERBS, key=len, reverse=True)) + r")\b",
    re.I,
)
DONE_RE = re.compile(_alt(P.DONE_CUES), re.I)
MIN_LEN = 30


def is_task(s: str) -> bool:
    """Does this sentence read like something the NPC wants you to do?"""
    s = s.strip()
    if len(s) < MIN_LEN or DONE_RE.search(s):
        return False
    if REQUEST_RE.search(s):  # explicit request wins, even when phrased as a question
        return True
    if NOISE_RE.search(s) or s.endswith("?"):
        return False
    return bool(PHRASE_RE.search(s) or IMPERATIVE_RE.search(s))


ZONE_NAMES = {
    "nightharbore": "Night Harbor East",
    "nightharborw": "Night Harbor West",
    "shadeddunes": "Shaded Dunes",
    "sungreetstrand": "Sungreet Strand",
    "saltbreezepark": "Saltbreeze Park",
    "faelindral": "Faelindral",
    "fallenpass": "Fallen Pass",
}

# A short task sentence that points at something said just before it ("head back down",
# "take this to him") gets the previous sentence prepended for context.
DANGLING_RE = re.compile(r"\b(down|up|back|there|here|it|him|her|them|their|its|that|those|these|the same)\b", re.I)
MAX_PREV_LINE = 200  # chars: borrow a whole previous line as context only if it is short
UNMATCHED_DAYS = timedelta(days=7)  # how far back unmatched.txt looks
LEDGER_EPOCH = datetime(2000, 1, 1)  # "all of it" for loot_since()
UNMATCHED_FILE = HERE / "unmatched.txt"

# Emote lines where the NPC hands you something. The captured item is shown under the NPC.
GIVE_RE = re.compile(
    r"\b(?:hands? you|handing you|gives? you|giving you|passes you|tosses|throws|offers you|offers it|"
    r"places|lays?|sets|slides|produces|pulls out|takes out|presents you with|presses)\s+"
    r"(?P<item>(?:a|an|the|some|two|three|several|his|her|its|another)\s+[^,.;]+?)"
    r"(?=\s+(?:into|in|to|on|onto|for|at|before|toward|towards|and|then|with|,|\.)|[,.]|$)",
    re.I,
)

# "gives you a generous nod" is not an item.
NOT_ITEM_RE = re.compile(
    r"\b(nod|look|glance|smile|grin|wink|once-over|moment|chance|word|warning|thanks|blessing|salute|wave|"
    r"shrug|laugh|chuckle|sigh|stare|glare|frown|scowl|kiss|hug|pat|slap|push|shove|hand|thought|idea|"
    r"lesson|choice|task|job|mission|reason|answer|question|name|story|tale|hint|clue|sign|signal)s?\b",
    re.I,
)

# "Bring me five of their bone chips": number + noun, used to count matching loot in the Ledger.
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "a dozen": 12, "dozen": 12, "twelve": 12, "fifteen": 15, "twenty": 20}
QTY_RE = re.compile(
    r"\b(?P<num>one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|a dozen|\d+)\s+"
    r"(?:of\s+(?:their|its|the|those|these|either|his|her)\s+)?"
    r"(?P<noun>[a-z]+(?:\s+[a-z]+){0,2})",
    re.I,
)
# "collect a fire beetle eye", "bring me an ogre tooth": a single item after a fetch verb.
SINGLE_RE = re.compile(
    r"\b(?:collect|gather|bring(?: me| back| us)?|fetch|get(?: me)?|find(?: me)?|retrieve|obtain|recover|"
    r"acquire|procure|kill|slay|hunt|harvest|pick up|grab)\s+(?:a|an|one)\s+(?P<noun>[a-z]+(?:\s+[a-z]+){0,2})",
    re.I,
)
GENERIC_NOUNS = {"portions", "portion", "pieces", "piece", "pairs", "pair", "samples", "sample", "sets", "set",
                 "bits", "bit", "units", "unit", "bundles", "bundle", "handfuls", "handful", "lots", "lot"}
TRAILING_WORDS = {"and", "then", "from", "for", "to", "so", "that", "of", "with", "in", "on", "or", "but", "if", "when",
                  "before", "after", "into", "back", "here", "there", "each", "every", "as", "at", "by", "which"}
STOP_NOUNS = {"part", "parts", "piece", "proof", "sample", "bit", "chance", "look", "hand", "word", "favor", "favour",
              "moment", "few", "little", "lot", "reason", "message", "way", "step", "steps", "trip", "visit",
              "of", "them", "more", "birds", "stone", "time", "thing", "things", "day", "days", "night", "nights",
              "way", "ways", "hour", "hours", "week", "weeks", "gold", "silver", "copper", "platinum", "coins", "coin"}


def singular(word: str) -> str:
    w = word.lower()
    irregular = {"teeth": "tooth", "feet": "foot", "geese": "goose", "mice": "mouse", "lice": "louse", "leaves": "leaf",
                 "knives": "knife", "wolves": "wolf", "halves": "half", "hooves": "hoof", "calves": "calf"}
    if w in irregular:
        return irregular[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "sses", "xes", "zes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _noun_words(raw: str) -> list[str]:
    """Cut a captured noun phrase at the first trailing/stop word: 'bat wings then' -> ['bat', 'wings']."""
    out: list[str] = []
    for w in raw.lower().split():
        if w in TRAILING_WORDS:
            break
        out.append(w)
    return out


def wanted_items(text: str) -> list[tuple[int, list[str], str]]:
    """Every 'N <things>' / 'collect a <thing>' in a task sentence, as
    (count, [singular noun words], phrase as the NPC said it)."""
    found: list[tuple[int, list[str], str]] = []
    seen_spans: list[tuple[int, int]] = []
    for m in QTY_RE.finditer(text):
        num = m.group("num").lower()
        count = NUMBER_WORDS.get(num) or (int(num) if num.isdigit() else 0)
        if count < 2:
            continue  # "one stone", "one properly": too ambiguous; singles come from SINGLE_RE
        words = _noun_words(m.group("noun"))
        if not words or words[0] in STOP_NOUNS:
            continue
        phrase = " ".join(words)
        if words[0] in GENERIC_NOUNS:
            # "six portions of either meat" -> the noun after "of"
            after = re.search(r"\b" + words[0] + r"\s+of\s+(?:either|the|their|its|some|any|fresh|raw|cooked)?\s*([a-z]+)",
                              text[m.start():], re.I)
            if not after:
                continue
            words = [after.group(1).lower()]
            phrase = f"{phrase} of {words[0]}"
        elif singular(words[-1]) == words[-1]:
            continue  # "two birds with": the head noun must be plural when asking for several
        found.append((count, [singular(w) for w in words if len(w) > 2], phrase))
        seen_spans.append(m.span())
    for m in SINGLE_RE.finditer(text):
        if any(a <= m.start("noun") < b for a, b in seen_spans):
            continue
        words = _noun_words(m.group("noun"))
        if not words or words[0] in STOP_NOUNS or words[-1] in GENERIC_NOUNS:
            continue
        if singular(words[-1]) != words[-1] and not words[-1].endswith("ss"):
            continue  # "collect a few samples": plural after "a" is not a single item
        found.append((1, [singular(w) for w in words if len(w) > 2], " ".join(words)))
    return found


def wanted_quantity(text: str) -> tuple[int, list[str]] | None:
    """First counted item, kept for callers that only need one."""
    items = wanted_items(text)
    return (items[0][0], items[0][1]) if items else None


def loot_since(char_dir: Path, when: datetime) -> list[tuple[datetime, str, int]]:
    """(time, item name, quantity) for corpse loot after `when`, from the Ledger."""
    out: list[tuple[datetime, str, int]] = []
    ledger = char_dir / "Ledger"
    if not ledger.is_dir():
        return out
    for f in ledger.glob("*.json"):
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for e in data.get("c01", []):
            act = e.get("f01")
            # act_13 = looted from a corpse (+), act_24 = sold to a vendor (-), act_11 = dropped (-).
            # Hand-ins to NPCs are not logged by the game, so those cannot be subtracted.
            sign = {"act_13": 1, "act_24": -1, "act_11": -1}.get(act)
            if sign is None:
                continue
            try:
                t = datetime.fromisoformat(e["f04"]).replace(tzinfo=None)
                d = json.loads(e.get("f03") or "{}")
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
            if t >= when and d.get("d04"):
                out.append((t, d["d04"], sign * int(d.get("d01") or 1)))
    return out


def match_loot(nouns: list[str], must_intact: bool, loot: list[tuple[datetime, str, int]],
               text_words: set[str] = frozenset()) -> tuple[int, str]:
    """(quantity looted, most common matching loot name) for one required item.

    Candidates share the head noun ("leg") and any modifiers ("bat" in "bat wings").
    When the NPC's text names the creature ("grain beetles ... six of their legs"), loot
    names whose other words appear in that text win over ones that do not, so
    "Intact Grain Beetle Leg" is counted and "Scarab Leg" is not."""
    key = nouns[-1]  # last word is the head noun: "bone chips" -> chip, "bat wings" -> wing
    per_name: dict[str, int] = {}
    score: dict[str, int] = {}
    for _, name, qty in loot:
        words = [singular(w) for w in re.findall(r"[a-z]+", name.lower())]
        if key not in words:
            continue
        if len(nouns) > 1 and not all(n in words for n in nouns[:-1]):
            continue  # "bat wings" should not count "moth wings"
        if must_intact and "broken" in words:
            continue
        per_name[name] = per_name.get(name, 0) + qty
        score[name] = sum(1 for w in words if w != key and w in text_words)
    if not per_name:
        return 0, ""
    top = max(score.values())
    if top > 0:
        per_name = {n: q for n, q in per_name.items() if score[n] == top}
    have = sum(per_name.values())
    best = max(per_name, key=per_name.get)
    return max(have, 0), best


def task_items(task_text: str, loot: list[tuple[datetime, str, int]]) -> list[Item]:
    must_intact = bool(re.search(r"\bintact\b", task_text, re.I))
    text_words = {singular(w) for w in re.findall(r"[a-z]+", task_text.lower())}
    items: list[Item] = []
    for count, nouns, phrase in wanted_items(task_text):
        if not nouns:
            continue
        have, loot_name = match_loot(nouns, must_intact, loot, text_words)
        name = loot_name or (("intact " if must_intact else "") + phrase)
        items.append(Item(name, count, have))
    return items


def loot_progress(task_text: str, loot: list[tuple[datetime, str, int]]) -> str:
    items = task_items(task_text, loot)
    if not items:
        return ""
    return f"{min(sum(i.have for i in items), sum(i.want for i in items))}/{sum(i.want for i in items)}"


def write_unmatched(data: "dict[str, list[Npc]]") -> None:
    """Every recent NPC sentence the tool did NOT treat as a task. If a quest was
    missed, this is the file to send along so the phrase library can be extended."""
    lines = ["# NPC sentences from the last 7 days that were not treated as tasks.",
             "# If one of these was a quest, send this file to whoever maintains the phrase library.", ""]
    for char, npcs in data.items():
        rows = sorted(((when, npc.name, s) for npc in npcs for when, s in npc.unmatched), reverse=True)
        if not rows:
            continue
        lines.append(f"## {char}")
        lines += [f"{when:%m-%d %H:%M} {name}: {s}" for when, name, s in rows]
        lines.append("")
    try:
        UNMATCHED_FILE.write_text("\n".join(lines), "utf-8")
    except OSError:
        pass
# A task sentence that announces a list ("collect the following...") gets the next
# sentences / lines appended.
CONTINUES_RE = re.compile(r"(\.\.\.|:)\s*$|\b(the following|as follows|these items|this list)\b", re.I)
CONTINUATION_WINDOW = timedelta(minutes=3)
MAX_CONTINUATION_LINES = 3


def pretty_zone(raw: str) -> str:
    if raw in ZONE_NAMES:
        return ZONE_NAMES[raw]
    return re.sub(r"[_-]+", " ", raw).title()

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}): (.*)$")
TAG_RE = re.compile(r"</?[ib]>")
MIN_LEN = 30


@dataclass
class Task:
    id: str
    char: str
    npc: str
    when: datetime
    text: str  # the task sentence, with neighbouring context folded in where it helps
    status: str = "open"  # open | likely-done | done | hidden
    zone: str = ""
    context: str = ""  # the surrounding NPC lines, for click-to-expand in the overlay
    progress: str = ""  # e.g. "2/6" when the Ledger shows matching loot since the task was given
    items: list["Item"] = field(default_factory=list)  # required items with their own counters


@dataclass
class Item:
    name: str  # loot name when the Ledger has seen it, else the phrase from the NPC
    want: int
    have: int

    @property
    def done(self) -> bool:
        return self.have >= self.want

    @property
    def counter(self) -> str:
        return f"{min(self.have, self.want)}/{self.want}"


@dataclass
class Npc:
    char: str
    name: str
    last_seen: datetime
    tasks: list[Task] = field(default_factory=list)
    zone: str = ""
    turn_ins: list[tuple[datetime, str]] = field(default_factory=list)  # reward/thanks lines
    unmatched: list[tuple[datetime, str]] = field(default_factory=list)  # recent sentences not treated as tasks
    given: list[tuple[datetime, str]] = field(default_factory=list)  # items the NPC handed you (from emotes)


# ---------------------------------------------------------------- state

def load_state() -> dict:
    state = {"done": {}, "hidden": [], "reopened": []}
    if STATE_FILE.exists():
        state.update(json.loads(STATE_FILE.read_text("utf-8")))
    return state


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), "utf-8")


# ---------------------------------------------------------------- ledger -> zone timeline

def zone_timeline(char_dir: Path) -> list[tuple[datetime, str]]:
    """(timestamp, zone name) pairs from the Ledger, so NPC chats can be placed in a zone."""
    out: list[tuple[datetime, str]] = []
    ledger = char_dir / "Ledger"
    if not ledger.is_dir():
        return out
    for f in ledger.glob("*.json"):
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for e in data.get("c01", []):
            z = e.get("f05", "")
            ts = e.get("f04", "")
            if not z.startswith("zone_") or not ts:
                continue
            try:
                name = base64.b64decode(z[5:] + "=" * (-len(z[5:]) % 4)).decode("utf-8", "replace")
                when = datetime.fromisoformat(ts).replace(tzinfo=None)
            except (ValueError, UnicodeDecodeError):
                continue
            out.append((when, pretty_zone(name)))
    out.sort()
    return out


def zone_at(timeline: list[tuple[datetime, str]], when: datetime) -> str:
    best, best_dt = "", timedelta(minutes=45)
    for t, z in timeline:
        d = abs(t - when)
        if d < best_dt:
            best, best_dt = z, d
    return best


# ---------------------------------------------------------------- journal parsing

def split_sentences(text: str) -> list[str]:
    text = TAG_RE.sub("", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z<])", text)
    return [p.strip() for p in parts if p.strip()]


def parse_char(char_dir: Path, state: dict) -> list[Npc]:
    char = char_dir.name
    timeline = zone_timeline(char_dir)
    npcs: list[Npc] = []
    jdir = char_dir / "journal"
    if not jdir.is_dir():
        return npcs
    for f in sorted(jdir.iterdir()):
        if not f.is_file():
            continue
        name = f.name
        entries: list[tuple[datetime, str]] = []
        # The game occasionally glues two entries onto one line; split on embedded timestamps.
        text = re.sub(r"(?<!\n)(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}: )", "\n", f.read_text("utf-8-sig", errors="replace"))
        for raw in text.splitlines():
            m = LINE_RE.match(raw)
            if not m:
                continue
            entries.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), m.group(2)))
        if not entries:
            continue
        entries.sort()
        npc = Npc(char, name, entries[-1][0], zone=zone_at(timeline, entries[-1][0]))
        last_done: datetime | None = None
        # (when, sentences) for every "says" line, in order, so tasks can borrow context.
        says: list[tuple[datetime, list[str]]] = []
        for when, line in entries:
            body = line[len(name):].strip()
            if DONE_RE.search(body):
                last_done = when
                npc.turn_ins.append((when, TAG_RE.sub("", body)))
            if body.startswith("says "):
                says.append((when, split_sentences(body[5:])))
            else:
                # Emote line: does the NPC hand you something? ("hands you a small key", "places a filthy bag on the bar")
                g = GIVE_RE.search(TAG_RE.sub("", body))
                if g:
                    item = g.group("item").strip(" ,.")
                    if item and len(item) < 60 and not NOT_ITEM_RE.search(item):
                        npc.given.append((when, item))

        cutoff = datetime.now() - UNMATCHED_DAYS
        for i, (when, sentences) in enumerate(says):
            for j, s in enumerate(sentences):
                if not is_task(s):
                    if len(s) >= MIN_LEN and when >= cutoff and not s.endswith("?"):
                        npc.unmatched.append((when, s))
                    continue
                text = s
                # Context before: "Take this tunic and head back down." / "six of their legs"
                # -> add the nearest earlier statement, skipping questions and other tasks.
                if len(s) < 90 and DANGLING_RE.search(s):
                    prev = ""
                    follows_task = False  # an earlier task in the same line already gives the context
                    for cand in reversed(sentences[:j]):
                        if is_task(cand):
                            follows_task = True
                            break
                        if not cand.endswith("?"):
                            prev = cand
                            break
                    if not prev and not follows_task and i > 0 and when - says[i - 1][0] <= CONTINUATION_WINDOW:
                        line = [x for x in says[i - 1][1] if not is_task(x) and not x.endswith("?")]
                        joined = " ".join(line)
                        prev = joined if len(joined) <= MAX_PREV_LINE else (line[-1] if line else "")
                    if prev:
                        text = prev + " " + s
                # Context after: "collect the following..." -> add what follows, across lines if needed.
                if CONTINUES_RE.search(s):
                    tail: list[str] = [x for x in sentences[j + 1:] if not is_task(x)]
                    k, added = i + 1, 0
                    while (not tail or CONTINUES_RE.search(tail[-1])) and k < len(says) \
                            and added < MAX_CONTINUATION_LINES and says[k][0] - when <= CONTINUATION_WINDOW:
                        tail += [x for x in says[k][1] if not is_task(x)]
                        k, added = k + 1, added + 1
                    if tail:
                        text = text + " " + " ".join(tail)
                # Full surrounding lines for the overlay's click-to-expand.
                around = [" ".join(says[k][1]) for k in range(max(0, i - 1), min(len(says), i + 2))
                          if abs(says[k][0] - when) <= CONTINUATION_WINDOW]
                tid = hashlib.sha1(f"{char}|{name}|{s}".encode()).hexdigest()[:6]
                npc.tasks.append(Task(tid, char, name, when, text, zone=npc.zone, context="\n".join(around)))
        for t in npc.tasks:
            if wanted_items(t.text):
                # Whole Ledger history, not just since the task: you may already carry the items.
                # Net = looted - sold - dropped is the best estimate of what is in your bags.
                t.items = task_items(t.text, loot_since(char_dir, LEDGER_EPOCH))
                if t.items:
                    t.progress = f"{min(sum(i.have for i in t.items), sum(i.want for i in t.items))}/{sum(i.want for i in t.items)}"
            if t.id in state["hidden"]:
                t.status = "hidden"
            elif t.id in state["done"]:
                t.status = "done"
            elif last_done and t.when < last_done and t.id not in state["reopened"]:
                t.status = "likely-done"
        if npc.tasks or npc.turn_ins or npc.unmatched or npc.given:
            npcs.append(npc)
    npcs.sort(key=lambda n: n.last_seen, reverse=True)
    return npcs


def parse_all(state: dict, only_char: str | None = None) -> dict[str, list[Npc]]:
    root = GAME_DIR / SERVER
    result: dict[str, list[Npc]] = {}
    if not root.is_dir():
        sys.exit(f"Game data folder not found: {root}")
    for d in sorted(root.iterdir()):
        if d.is_dir() and (not only_char or d.name.lower() == only_char.lower()):
            result[d.name] = parse_char(d, state)
    return result


# ---------------------------------------------------------------- rendering

def render_md(data: dict[str, list[Npc]], show_all: bool = False) -> str:
    lines = [f"# Monsters & Memories quests  \n_updated {datetime.now():%Y-%m-%d %H:%M}_", ""]
    for char, npcs in data.items():
        lines.append(f"## {char}")
        any_out = False
        for npc in npcs:
            tasks = [t for t in npc.tasks if show_all or t.status == "open"]
            if not tasks:
                continue
            any_out = True
            zone = f" ({npc.zone})" if npc.zone else ""
            lines.append(f"\n### {npc.name}{zone} - last spoke {npc.last_seen:%b %d %H:%M}")
            for when, item in npc.given:
                lines.append(f"- gave you: {item} ({when:%b %d %H:%M})")
            for t in tasks:
                mark = {"open": "[ ]", "likely-done": "[~]", "done": "[x]", "hidden": "[-]"}[t.status]
                lines.append(f"- {mark} `{t.id}` {t.text}")
                for it in t.items:
                    lines.append(f"  - {'[x]' if it.done else '[ ]'} {it.name} **{it.counter}**")
        if not any_out:
            lines.append("_nothing open_")
        if show_all:
            recent = sorted(
                ((when, npc.name, text) for npc in npcs for when, text in npc.turn_ins),
                reverse=True,
            )[:10]
            if recent:
                lines.append("\n### Recent turn-ins / thanks (match these to open tasks by hand)")
                for when, name, text in recent:
                    lines.append(f"- {when:%b %d %H:%M} {name}: {text}")
        lines.append("")
    return "\n".join(lines)


def active_character() -> str | None:
    """The character whose folder the game touched most recently (journal, ledger, UI layout)."""
    root = GAME_DIR / SERVER
    best, best_t = None, 0
    for d in root.iterdir():
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file():
                t = p.stat().st_mtime
                if t > best_t:
                    best, best_t = d.name, t
    return best


def open_tasks(npc: Npc) -> list[Task]:
    return [t for t in npc.tasks if t.status == "open"]


def render_notes_block(data: dict[str, list[Npc]], active: str | None, help_text: bool = False) -> str:
    """Compact plain text for the in-game /note window.

    The active character's quests are listed in full; other characters are
    collapsed to a count so the shared note stays short.
    """
    out = [
        BLOCK_START,
        f"updated {datetime.now():%b %d %H:%M}",
        "finished a task? change its leading '-' to 'x' (or 'h' to hide it), then close this window",
        "type  /mobetta help  on its own line above for all commands",
    ]
    if help_text:
        out += ["", HELP_TEXT]
    ordered = sorted(data, key=lambda c: (c != active, c))
    others: list[str] = []
    for char in ordered:
        npcs = data[char]
        n_open = sum(len(open_tasks(npc)) for npc in npcs)
        if char != active:
            others.append(f"{char} {n_open}")
            continue
        out += ["", f"== {char} ({n_open} open) =="]
        for npc in npcs:
            tasks = open_tasks(npc)
            if not tasks:
                continue
            zone = f" [{npc.zone}]" if npc.zone else ""
            out.append(f"* {npc.name}{zone}")
            if npc.given:
                out.append("  gave you: " + ", ".join(item for _, item in npc.given[-3:]))
            for t in tasks:
                out.append(f"  - ({t.id}) {t.text}")
                for it in t.items:
                    out.append(f"      {'x' if it.done else '.'} {it.name}  {it.counter}")
    if others:
        out += ["", "other chars: " + ", ".join(others)]
    out.append(BLOCK_END)
    return "\n".join(out)


def _strip_stamp(block: str) -> str:
    return "\n".join(l for l in block.split("\n") if not l.startswith("updated "))


def read_notes() -> tuple[str, str, str]:
    """Split notes.txt into (user text before block, current block or '', text after block)."""
    existing = NOTES_FILE.read_text("utf-8") if NOTES_FILE.exists() else ""
    existing = existing.replace("\r\n", "\n")
    for start, end in [(BLOCK_START, BLOCK_END)] + OLD_MARKERS:
        if start in existing and end in existing:
            a = existing.index(start)
            b = existing.index(end) + len(end)
            return existing[:a], existing[a:b], existing[b:]
    return existing, "", ""


def write_notes(block: str, pre: str | None = None, post: str | None = None) -> bool:
    """Append/replace the block. Returns False if the file already had this exact block."""
    cur_pre, current, cur_post = read_notes()
    if pre is None:
        pre = cur_pre
    if post is None:
        post = cur_post
    if current and _strip_stamp(current) == _strip_stamp(block) and pre == cur_pre and post == cur_post:
        return False
    pre = pre.rstrip("\n")
    body = (pre + "\n\n" if pre else "") + block + ("\n" + post.lstrip("\n") if post.strip() else "\n")
    # Match the game's own format: UTF-8, no BOM, LF newlines.
    with open(NOTES_FILE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    return True


# Corrections typed inside the game's /note window.
#   In your own notes area:   done 8c38db   /   hide 8c38db   /   undo 8c38db
#   Inside the block:         x (8c38db) ...   or   - (8c38db) ... x
#   App commands:             /mobetta open   /   /mobetta help   (see HELP_TEXT); /mnmquest and /mbq also work
CMD_RE = re.compile(r"^\s*(done|hide|undo|x)\s+\(?([0-9a-f]{6})\)?\s*$", re.I)
APP_CMD_RE = re.compile(r"^\s*/(?:mobetta(?:quests?)?|mbq|mnmquests?)\s+(\w+)(?:\s+(\S+))?\s*$", re.I)
TASK_VERBS = ("done", "undo", "x")

HELP_TEXT = """/mobetta commands (/mbq works too) - type one on its own line up here, then close this window:
  open | hide | toggle     show / hide the overlay (hotkey Ctrl+Shift+Q)
  reload                   rebuild this list right now
  done <id>  undo <id>     finish / reopen a task (ids are the codes below)
  hide <id>                never show that line again
  char <name> | auto       pin the overlay to one character / follow the game
  startup on | off         start with Windows
  quit                     close the app
  help                     show this text (goes away on the next command)"""
MARK_RE = re.compile(r"^\s*([xX+]|-\s*[xX]|\[[xX]\])\s*\(([0-9a-f]{6})\)|^\s*-\s*\(([0-9a-f]{6})\).*\s(x|X|done)\s*$")
HIDE_MARK_RE = re.compile(r"^\s*[hH]\s*\(([0-9a-f]{6})\)")


def apply_note_corrections(state: dict) -> list[tuple[str, str | None]]:
    """Read commands the player typed in /note. Task corrections are applied to
    state and stripped from the player's notes. App commands (/mnmquest ...) are
    stripped too and returned as (verb, arg) for the overlay app to act on."""
    pre, block, post = read_notes()
    changed = False
    app_cmds: list[tuple[str, str | None]] = []
    kept: list[str] = []
    for line in pre.split("\n"):
        m = CMD_RE.match(line)
        if m:
            verb, tid = m.group(1).lower(), m.group(2)
            _apply(state, "done" if verb == "x" else verb, tid)
            changed = True
            continue
        m = APP_CMD_RE.match(line)
        if m:
            verb, arg = m.group(1).lower(), m.group(2)
            if verb in TASK_VERBS or (verb == "hide" and arg and re.fullmatch(r"[0-9a-f]{6}", arg)):
                _apply(state, "done" if verb == "x" else verb, arg or "")
            else:
                app_cmds.append((verb, arg))
            changed = True
            continue
        kept.append(line)
    for line in block.split("\n"):
        m = MARK_RE.match(line)
        if m:
            _apply(state, "done", m.group(2) or m.group(3))
            changed = True
            continue
        m = HIDE_MARK_RE.match(line)
        if m:
            _apply(state, "hide", m.group(1))
            changed = True
    if changed:
        save_state(state)
        new_pre = "\n".join(kept)
        if new_pre != pre:
            write_notes(block or "", pre=new_pre, post=post)
    return app_cmds


def _apply(state: dict, verb: str, tid: str) -> None:
    state.setdefault("reopened", [])
    if verb == "done":
        state["done"][tid] = datetime.now().strftime("%Y-%m-%d")
        state["hidden"] = [h for h in state["hidden"] if h != tid]
        state["reopened"] = [r for r in state["reopened"] if r != tid]
    elif verb == "undo":
        # Clears a done/hidden mark, and also overrides an automatic "likely done".
        state["done"].pop(tid, None)
        state["hidden"] = [h for h in state["hidden"] if h != tid]
        state["reopened"] = sorted(set(state["reopened"]) | {tid})
    elif verb == "hide":
        state["hidden"] = sorted(set(state["hidden"]) | {tid})
        state["done"].pop(tid, None)
        state["reopened"] = [r for r in state["reopened"] if r != tid]
    print(f"{datetime.now():%H:%M:%S} {verb} {tid}")


# ---------------------------------------------------------------- commands

def cmd_write(state: dict, force_char: str | None = None) -> None:
    apply_note_corrections(state)
    data = parse_all(state)
    active = force_char or active_character()
    if active and active not in data:
        match = [c for c in data if c.lower() == active.lower()]
        active = match[0] if match else None
    MD_FILE.write_text(render_md(data, show_all=True), "utf-8")
    write_unmatched(data)
    changed = write_notes(render_notes_block(data, active))
    n = sum(len(open_tasks(npc)) for npcs in data.values() for npc in npcs)
    verb = "wrote" if changed else "already current:"
    print(f"{datetime.now():%H:%M:%S} {verb} {n} open task(s) in {NOTES_FILE.name} "
          f"(active: {active or 'unknown'})")


def snapshot() -> tuple:
    """mtimes of everything that should trigger a rebuild: journals, ledgers, UI
    layout (character switch), the game's own rewrite of notes.txt, and state.json."""
    root = GAME_DIR / SERVER
    files = [p for p in root.rglob("*") if p.is_file()]
    files += [p for p in (NOTES_FILE, STATE_FILE) if p.exists()]
    return tuple((str(p), p.stat().st_mtime_ns) for p in sorted(files))


def cmd_watch(state: dict, interval: float) -> None:
    last = None
    print(f"watching {GAME_DIR} every {interval:g}s (Ctrl+C to stop)")
    while True:
        try:
            cur = snapshot()
        except OSError:
            cur = None
        if cur != last:
            state = load_state()
            cmd_write(state)
            # Re-snapshot after our own write so it does not trigger another pass.
            try:
                last = snapshot()
            except OSError:
                last = None
        time.sleep(interval)


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(line_buffering=True)  # so watch output shows up when redirected
    state = load_state()
    cmd = argv[0] if argv else "list"
    args = argv[1:]
    if cmd == "list":
        print(render_md(parse_all(state, args[0] if args else None)))
    elif cmd == "all":
        print(render_md(parse_all(state, args[0] if args else None), show_all=True))
    elif cmd == "write":
        cmd_write(state, args[0] if args else None)
    elif cmd == "watch":
        cmd_watch(state, float(args[0]) if args else 20.0)
    elif cmd in ("done", "undo", "hide"):
        if not args:
            sys.exit("give at least one task id")
        for tid in args:
            _apply(state, cmd, tid)
        save_state(state)
        cmd_write(state)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
