"""Keep the wiki-derived data files (quests.json, items.json, npcs.json) fresh.

The files are scraped centrally (wiki_quests.py / wiki_data.py) and committed to the GitHub repo.
The app downloads a newer copy from there at most once a day, in a background thread, so no
player's machine ever crawls the wiki itself. A file next to the exe always wins over the copy
bundled inside it. Turn it off with `/mobetta updates off` (state.json: "updates": false).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import mnm_quests as mq

RAW = "https://raw.githubusercontent.com/amyklindley/mo-betta-quests/main/"
FILES = ("quests.json", "items.json", "npcs.json")
CHECK_EVERY = 24 * 3600  # seconds
STAMP = mq.HERE / "data-updates.json"  # {name: {"etag": ..., "checked": epoch}}


def _stamps() -> dict:
    try:
        return json.loads(STAMP.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def enabled() -> bool:
    return bool(mq.load_state().get("updates", True))


def refresh(force: bool = False, log=print) -> list[str]:
    """Download any data file that changed on GitHub. Returns the names that were updated."""
    if not force and not enabled():
        return []
    stamps = _stamps()
    updated: list[str] = []
    now = time.time()
    for name in FILES:
        st = stamps.get(name, {})
        if not force and now - st.get("checked", 0) < CHECK_EVERY and (mq.HERE / name).exists():
            continue
        req = urllib.request.Request(RAW + name, headers={"User-Agent": "MoBettaQuests (data refresh)"})
        if st.get("etag") and (mq.HERE / name).exists():
            req.add_header("If-None-Match", st["etag"])
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                etag = r.headers.get("ETag", "")
            json.loads(body)  # refuse anything that is not valid JSON
            tmp = mq.HERE / (name + ".tmp")
            tmp.write_bytes(body)
            tmp.replace(mq.HERE / name)
            stamps[name] = {"etag": etag, "checked": now}
            updated.append(name)
            log(f"data refresh: {name} updated ({len(body) // 1024} KB)")
        except urllib.error.HTTPError as e:
            if e.code == 304:
                stamps[name] = {"etag": st.get("etag", ""), "checked": now}
            else:
                log(f"data refresh: {name} skipped (HTTP {e.code})")
        except Exception as e:  # noqa: BLE001  (offline is normal; try again tomorrow)
            log(f"data refresh: {name} skipped ({e.__class__.__name__})")
    try:
        STAMP.write_text(json.dumps(stamps), "utf-8")
    except OSError:
        pass
    return updated
