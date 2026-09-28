#!/usr/bin/env python3
"""Pull item and NPC/mob pages from the Monsters & Memories community wiki into items.json and npcs.json.

Source: https://monstersandmemories.miraheze.org  (Category:Items, Category:NPCs).
Pages are fetched 50 at a time through the API's revisions generator, so a full refresh is about
150 requests rather than 7,000. Wiki text is community-written; each file keeps the source and
fetch date for credit.

  python wiki_data.py            fetch both
  python wiki_data.py items      just items.json
  python wiki_data.py npcs       just npcs.json
  python wiki_data.py zones      just zones.json
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
        "image_file": ("File:" + plain(box.get("icon_id", "")) + ".png") if plain(box.get("icon_id", "")) else "",
        "image": "",  # filled in by dump() from image_file
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

def image_urls(file_titles: list[str]) -> dict[str, str]:
    """{'File:X.png': 'https://static...'} for wiki files, 50 per request. Missing files are left out."""
    out: dict[str, str] = {}
    titles = sorted({t for t in file_titles if t})
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        r = api(action="query", prop="imageinfo", iiprop="url", titles="|".join(chunk))
        for p in r.get("query", {}).get("pages", []):
            info = p.get("imageinfo") or []
            if info and info[0].get("url"):
                out[p["title"]] = info[0]["url"]
        # the API normalises titles (first letter upper-cased, underscores); map the originals too
        for n in r.get("query", {}).get("normalized", []):
            if n["to"] in out:
                out[n["from"]] = out[n["to"]]
    return out


def file_title(name: str) -> str:
    name = (name or "").strip()
    if not name or re.search(r"phicon|placeholder", name, re.I):
        return ""
    name = re.sub(r"^\[\[File:|\]\]$", "", name).split("|")[0].strip()
    return "File:" + name if not name.lower().startswith("file:") else name


def parse_npc(title: str, text: str) -> dict | None:
    kind = "npc"
    box = template(text, "Namedmobpage") or template(text, "Mobpage") or template(text, "NPCpage")
    if box is None:
        box = template(text, "Merchantpage")
        kind = "merchant"
    if box is None:
        return None
    bullets = [plain(re.sub(r"^\*+\s*", "", l)) for l in (box.get("buys") or "").splitlines() if l.strip().startswith("*")]
    return {
        "title": title,
        "kind": kind,
        "image_file": file_title(box.get("imagefilename", "")),
        "image": "",  # filled in by dump() from image_file
        "name": title,  # the page title is the in-game name; captions are sometimes descriptions or photo credits
        "caption": plain(box.get("caption", "")) if not re.search(r"place ?holder", box.get("caption", ""), re.I) else "",
        "sells": links(box.get("sells", "")),
        "buys": bullets,
        "dialog": plain(box.get("dialog", ""))[:600],
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


# ---------------------------------------------------------------- zones

def parse_zone(title: str, text: str) -> dict | None:
    box = template(text, "ZoneDetails")
    if box is None:
        return None
    # description: the first prose line before the template
    intro = ""
    for line in text.split("{{ZoneDetails")[0].splitlines():
        raw = line.strip()
        if not raw or raw.startswith(("[[File:", "__", "<", "{{", "|")) or "thumb" in raw:
            continue
        s = plain(raw)
        if len(s) > 20:
            intro = s
            break
    files = re.findall(r"\[\[File:([^\]|]+)", text)
    image = next((f for f in files if "map" not in f.lower()), "")
    map_img = next((f for f in files if "map" in f.lower()), "")
    return {
        "title": title,
        "name": title,
        "description": intro,
        "level": plain(box.get("level", "")).strip(" -") or "",
        "monsters": [m.strip() for m in plain(box.get("monstertypes", "")).split(",") if m.strip()],
        "notable_npcs": links(box.get("notablenpc", "")),
        "notable_items": links(box.get("items", "")),
        "quests": links(box.get("relatedquests", "")),
        "adjacent": links(box.get("adjacentzones", "")),
        "image_file": "File:" + image.strip() if image else "",
        "map_file": "File:" + map_img.strip() if map_img else "",
        "image": "",
        "map": "",
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
    # resolve wiki image files to URLs, 50 per request
    wanted = [r.get("image_file", "") for r in rows] + [r.get("map_file", "") for r in rows]
    urls = image_urls([w for w in wanted if w])
    for r in rows:
        r["image"] = urls.get(r.get("image_file", ""), "")
        if "map_file" in r:
            r["map"] = urls.get(r.get("map_file", ""), "")
    print(f"  {name}: {sum(1 for r in rows if r.get('image'))} images resolved")
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
    if what in ("all", "zones"):
        dump("zones", "Category:Zones", parse_zone, lambda r: r["name"].lower())


if __name__ == "__main__":
    main(sys.argv[1:])
