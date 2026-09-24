#!/usr/bin/env python3
"""Pull item and NPC/mob pages from the Monsters & Memories community wiki into items.json and npcs.json.

Source: https://monstersandmemories.miraheze.org  (Category:Items, Category:NPCs).
Pages are fetched 50 at a time through the API's revisions generator, so a full refresh is about
150 requests rather than 7,000. Wiki text is community-written; each file keeps the source and
fetch date for credit.

  python wiki_data.py            fetch both
  python wiki_data.py items      just items.json
  python wiki_data.py npcs       just npcs.json
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

API = "https://monstersandmemories.miraheze.org/w/api.php?"
WIKI = "https://monstersandmemories.miraheze.org/wiki/"
UA = "MoBettaQuests/0.4 (community quest overlay; data refresh)"
HERE = Path(__file__).resolve().parent

LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"<[^>]+>")


def api(**params) -> dict:
    params.update(format="json", formatversion=2)
    req = urllib.request.Request(API + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    time.sleep(0.3)  # be polite to a volunteer-run wiki
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(3)
    return {}


def pages_in(category: str):
    """Yield (title, wikitext) for every page in a category, 50 per request."""
    cont: dict = {}
    while True:
        r = api(action="query", generator="categorymembers", gcmtitle=category, gcmlimit=50, gcmnamespace=0,
                prop="revisions", rvprop="content", rvslots="main", **cont)
        for p in r.get("query", {}).get("pages", []):
            revs = p.get("revisions") or []
            if revs:
                yield p["title"], revs[0]["slots"]["main"]["content"]
        if "continue" not in r:
            return
        cont = r["continue"]


def plain(s: str) -> str:
    s = LINK_RE.sub(lambda m: m.group(2) or m.group(1), s or "")
    s = TAG_RE.sub("", s).replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip()


def template(text: str, name: str) -> dict[str, str] | None:
    """Fields of {{Name | a = .. | b = .. }} as {lowercase key: raw value}. Handles nested [[links]] and multi-line values."""
    m = re.search(r"\{\{\s*" + re.escape(name) + r"\b", text, re.I)
    if not m:
        return None
    i, depth, start = m.end(), 1, m.end()
    while i < len(text) and depth:
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i):
            depth -= 1
            i += 2
        else:
            i += 1
    body = text[start:i - 2]
    fields: dict[str, str] = {}
    # split on | that are not inside [[ ]]
    parts, buf, lvl = [], "", 0
    for ch_i, ch in enumerate(body):
        if body.startswith("[[", ch_i):
            lvl += 1
        elif body.startswith("]]", ch_i) and lvl:
            lvl -= 1
        if ch == "|" and lvl == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            fields[k.strip().lower()] = v.strip()
    return fields


def links(raw: str) -> list[str]:
    return [m.group(2) or m.group(1) for m in LINK_RE.finditer(raw or "")]


def grouped_links(raw: str) -> list[dict]:
    """'[[Zone]]\n* [[mob]]\n* [[mob]]' -> [{'zone': 'Zone', 'mobs': [...]}, ...]"""
    out: list[dict] = []
    current: dict | None = None
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("*"):
            names = links(line)
            if current is None:
                current = {"zone": "", "mobs": []}
                out.append(current)
            current["mobs"] += names
        else:
            names = links(line)
            if names:
                current = {"zone": names[0], "mobs": []}
                out.append(current)
    return out


# ---------------------------------------------------------------- items

STAT_KEYS = ["ac", "dmg", "delay", "hp", "mana", "str", "sta", "agi", "dex", "int", "wis", "cha",
             "cr", "cor", "dr", "er", "fr", "mr", "pr", "hr", "haste"]


def parse_item(title: str, text: str) -> dict | None:
    box = template(text, "ItemBox")
    if box is None:
        return None
    page = template(text, "Itempage") or {}
    stats = {k: plain(box[k]) for k in STAT_KEYS if box.get(k, "").strip()}
    flags = [k for k in ("magic", "lore", "unique", "nodrop", "norent", "nozone") if box.get(k, "").strip()]
    return {
        "title": title,
        "name": plain(box.get("item_name", "")) or title,
        "id": plain(box.get("item_link_id", "")),
        "icon": plain(box.get("icon_id", "")),
        "slot": plain(box.get("slot", "")),
        "skill": plain(box.get("skill", "")),
        "classes": plain(box.get("class", "")),
        "races": plain(box.get("race", "")),
        "weight": plain(box.get("weight", "")),
        "size": plain(box.get("size", "")),
        "effect": plain(box.get("effect", "")),
        "description": plain(box.get("item_stats", "")),
        "flags": flags,
        "stats": stats,
        "drops_from": grouped_links(page.get("dropsfrom", "")),
        "sold_by": links(page.get("soldby", "")) + links(page.get("sold_by", "")) + links(page.get("vendors", "")),
        "quest_reward": links(page.get("questreward", "")) + links(page.get("quest_reward", "")) + links(page.get("quests", "")),
        "url": WIKI + urllib.parse.quote(title.replace(" ", "_")),
    }


# ---------------------------------------------------------------- npcs / mobs

def parse_npc(title: str, text: str) -> dict | None:
    box = template(text, "Namedmobpage") or template(text, "Mobpage") or template(text, "NPCpage")
    if box is None:
        return None
    return {
        "title": title,
        "name": plain(box.get("caption", "")) or title,
        "race": plain(box.get("race", "")),
        "class": plain(box.get("class", "")),
        "level": plain(box.get("level", "")),
        "zone": plain(box.get("zone", "")),
        "location": plain(box.get("location", "")),
        "description": plain(box.get("description", "")),
        "hp": plain(box.get("hp", "")),
        "loot": links(box.get("common_loot", "")) + links(box.get("known_loot", "")) + links(box.get("rare_loot", "")),
        "factions": links(box.get("factions", "")),
        "opposing_factions": links(box.get("opposing_factions", "")),
        "quests": links(box.get("related_quests", "")),
        "url": WIKI + urllib.parse.quote(title.replace(" ", "_")),
    }


def dump(name: str, category: str, parser, key_of) -> None:
    rows, n_pages = [], 0
    for title, text in pages_in(category):
        n_pages += 1
        row = parser(title, text)
        if row:
            rows.append(row)
        if n_pages % 500 == 0:
            print(f"  {name}: {n_pages} pages...")
    rows.sort(key=key_of)
    out = HERE / f"{name}.json"
    out.write_text(json.dumps({"source": WIKI + category.replace(" ", "_"), "fetched": str(date.today()), name: rows},
                              ensure_ascii=False), "utf-8")
    print(f"wrote {out.name}: {len(rows)} of {n_pages} pages parsed")


def main(argv: list[str]) -> None:
    what = argv[0] if argv else "all"
    if what in ("all", "items"):
        dump("items", "Category:Items", parse_item, lambda r: r["name"].lower())
    if what in ("all", "npcs"):
        dump("npcs", "Category:NPCs", parse_npc, lambda r: r["name"].lower())


if __name__ == "__main__":
    main(sys.argv[1:])
