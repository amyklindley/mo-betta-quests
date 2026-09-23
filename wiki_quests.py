#!/usr/bin/env python3
"""Pull quest walkthroughs from the Monsters & Memories community wiki into quests.json.

Source: https://monstersandmemories.miraheze.org  Category:Quests and its class sub-categories.
Wiki text is community-written; quests.json keeps the page URL and fetch date for credit.

  python wiki_quests.py            fetch and write quests.json next to this script
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
UA = "MoBettaQuests/0.2 (community quest overlay)"
HERE = Path(__file__).resolve().parent
OUT = HERE / "quests.json"

LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"<[^>]+>")
BOLD_RE = re.compile(r"'''(.+?)'''")
SAYS_RE = re.compile(r"^:*\s*(?:<[^>]+>)?\s*([A-Z][^\"]{1,60}?) says,?\s*[\"“](.+?)[\"”]\s*(?:<[^>]+>)?\s*$")
YOU_SAY_RE = re.compile(r"^:*\s*You say,?\s*[\"“](.+?)[\"”]")
RECEIVE_RE = re.compile(r"You receive \[\[([^\]|]+)(?:\|[^\]]+)?\]\](?: x(\d+))? from \[\[([^\]|]+)")
HAND_RE = re.compile(r"\b(?:hand(?: in| over)?|give|turn in|deliver|return|bring)\s+(?:the\s+|a\s+|an\s+)?(\d+)?\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", re.I)


def api(**params) -> dict:
    params.update(format="json", formatversion=2)
    req = urllib.request.Request(API + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    time.sleep(0.3)  # be polite to a volunteer-run wiki
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def members(cat: str) -> list[dict]:
    out, cont = [], {}
    while True:
        r = api(action="query", list="categorymembers", cmtitle=cat, cmlimit=500, **cont)
        out += r["query"]["categorymembers"]
        if "continue" not in r:
            return out
        cont = r["continue"]


def quest_titles() -> list[str]:
    pages: set[str] = set()
    todo, seen = ["Category:Quests"], set()
    while todo:
        cat = todo.pop()
        if cat in seen:
            continue
        seen.add(cat)
        for m in members(cat):
            if m["ns"] == 0:
                pages.add(m["title"])
            elif m["ns"] == 14:
                todo.append(m["title"])
    return sorted(pages)


def wikitext(title: str) -> str:
    return api(action="parse", page=title, prop="wikitext")["parse"]["wikitext"]


def plain(s: str) -> str:
    s = LINK_RE.sub(lambda m: m.group(2) or m.group(1), s)
    s = TAG_RE.sub("", s)
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    return re.sub(r"\s+", " ", s).strip(" :")


def parse(title: str, text: str) -> dict:
    q = {"title": title, "url": WIKI + urllib.parse.quote(title.replace(" ", "_")), "zone": "", "giver": "",
         "min_level": "", "classes": "", "related": [], "rewards": [], "steps": [], "lines": [], "fetched": str(date.today())}
    box = re.search(r"\{\{Quest\s*(.*?)\n\}\}", text, re.S)
    if box:
        for k, v in re.findall(r"\|\s*([^=\n]+?)\s*=\s*([^\n]*)", box.group(1)):
            k, v = k.lower(), plain(v).strip(" -")
            if k == "start zone": q["zone"] = v
            elif k == "quest giver": q["giver"] = v
            elif k == "minimum level": q["min_level"] = v
            elif k == "classes": q["classes"] = v
            elif k == "related npcs": q["related"] = [x.strip() for x in v.split(",") if x.strip()]
    section = ""
    part = ""
    order = 0
    for raw in text.splitlines():
        line = raw.strip()
        h = re.match(r"^(=+)\s*(.+?)\s*=+$", line)
        if h:
            name = plain(h.group(2))
            if len(h.group(1)) == 2:
                section = name.lower()
            elif len(h.group(1)) >= 3 and section.startswith("walk"):
                part = name
            continue
        if section.startswith("reward"):
            if line.startswith("*") or "<li>" in line:
                r = plain(re.sub(r"^\*+\s*", "", line))
                if r:
                    q["rewards"].append(r)
            continue
        if not section.startswith("walk"):
            continue
        m = YOU_SAY_RE.match(line)
        if m:
            order += 1
            q["lines"].append({"n": order, "kind": "say", "text": plain(m.group(1)), "part": part})
            continue
        m = SAYS_RE.match(plain(line) if line.startswith(":") else line)
        if m:
            order += 1
            q["lines"].append({"n": order, "kind": "npc", "npc": plain(m.group(1)), "text": plain(m.group(2)), "part": part})
            continue
        for rm in RECEIVE_RE.finditer(line):
            order += 1
            q["lines"].append({"n": order, "kind": "receive", "item": rm.group(1), "qty": int(rm.group(2) or 1), "npc": rm.group(3), "part": part})
        for b in BOLD_RE.findall(line):
            step = plain(b)
            if len(step) < 8 or step.lower().startswith("note"):
                continue
            order += 1
            items = [{"name": n, "qty": int(qty or 1)} for qty, n in HAND_RE.findall(b)]
            q["steps"].append({"n": order, "text": step, "part": part, "items": items})
            q["lines"].append({"n": order, "kind": "step", "text": step, "part": part, "items": items})
    npcs = {q["giver"]} | set(q["related"]) | {l["npc"] for l in q["lines"] if l["kind"] == "npc"}
    q["npcs"] = sorted(n for n in npcs if n)
    return q


def main() -> None:
    titles = quest_titles()
    print(f"{len(titles)} quest pages")
    quests = []
    for i, t in enumerate(titles, 1):
        try:
            q = parse(t, wikitext(t))
        except Exception as e:  # noqa: BLE001
            print(f"  skip {t}: {e}")
            continue
        quests.append(q)
        if i % 20 == 0:
            print(f"  {i}/{len(titles)}")
    OUT.write_text(json.dumps({"source": WIKI + "Category:Quests", "fetched": str(date.today()), "quests": quests},
                              indent=1, ensure_ascii=False), "utf-8")
    n_lines = sum(len(q["lines"]) for q in quests)
    print(f"wrote {OUT.name}: {len(quests)} quests, {sum(len(q['steps']) for q in quests)} steps, {n_lines} lines")


if __name__ == "__main__":
    main()
