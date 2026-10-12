"""Sanity-check a nightly wiki scrape before it's published, and DM the maintainer on Discord if it looks wrong.

Run by nightly-refresh.bat after the scrapers. Compares each data file's entry count with the previous
run (kept in data-counts.json) and with a floor. A file that is missing, unreadable, under the floor, or
down more than 30% on last time fails the check: the bat then skips the git push, so the bots keep the
last good data, and a DM goes out saying what's wrong. A clean run says nothing.

  python refresh_check.py          check, alert if bad, exit 1 if bad
  python refresh_check.py --test   just send a test DM to prove the alert works

Settings in alert.env next to this file (not in git):
  ALERT_USER_ID=<your Discord user id>
  ALERT_TOKEN_FILE=..\\mobetta-bot\\.env   (a .env holding DISCORD_TOKEN of a bot that shares a server with you)
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNTS = HERE / "data-counts.json"
FILES = {  # file -> (json key, lowest count that could possibly be right)
    HERE / "items.json": ("items", 3000),
    HERE / "npcs.json": ("npcs", 1000),
    HERE / "quests.json": ("quests", 50),
    HERE / "zones.json": ("zones", 15),
    HERE.parent / "mobetta-crafts" / "recipes.json": ("recipes", 600),
}
DROP = 0.30  # more than this much smaller than last time is suspicious


def env(path: Path) -> dict[str, str]:
    out = {}
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def counts_now() -> tuple[dict[str, int], list[str]]:
    counts, problems = {}, []
    for path, (key, floor) in FILES.items():
        try:
            n = len(json.loads(path.read_text("utf-8"))[key])
        except (OSError, ValueError, KeyError, TypeError) as e:
            problems.append(f"{path.name}: can't read it ({e.__class__.__name__})")
            continue
        counts[key] = n
        if n < floor:
            problems.append(f"{path.name}: only {n} {key} (anything under {floor} is wrong)")
    return counts, problems


def check() -> list[str]:
    counts, problems = counts_now()
    try:
        before = json.loads(COUNTS.read_text("utf-8"))
    except (OSError, ValueError):
        before = {}
    for key, n in counts.items():
        old = before.get(key)
        if old and n < old * (1 - DROP):
            problems.append(f"{key}: {n}, down from {old} last time")
    if not problems:
        COUNTS.write_text(json.dumps(counts | {"date": str(date.today())}, indent=1), "utf-8")
    return problems


def dm(text: str) -> str | None:
    """Send a Discord DM through the bot. Returns an error string, or None when it went out."""
    cfg = env(HERE / "alert.env")
    user_id = cfg.get("ALERT_USER_ID")
    token = env(HERE / cfg.get("ALERT_TOKEN_FILE", r"..\mobetta-bot\.env")).get("DISCORD_TOKEN")
    if not user_id or not token:
        return "alert.env needs ALERT_USER_ID, and ALERT_TOKEN_FILE must point at a .env with DISCORD_TOKEN"

    def post(url: str, body: dict) -> dict:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bot {token}", "Content-Type": "application/json", "User-Agent": "MoBettaRefreshCheck/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    try:
        channel = post("https://discord.com/api/v10/users/@me/channels", {"recipient_id": user_id})["id"]
        post(f"https://discord.com/api/v10/channels/{channel}/messages", {"content": text[:1900]})
        return None
    except urllib.error.HTTPError as e:
        return f"Discord said HTTP {e.code}: {e.read()[:200]!r}"
    except Exception as e:  # noqa: BLE001
        return f"{e.__class__.__name__}: {e}"


def main(argv: list[str]) -> int:
    if "--test" in argv:
        err = dm("🧪 Test from the wiki refresh check on your PC. If you can read this, nightly alerts work.")
        print("test DM failed: " + err if err else "test DM sent")
        return 1 if err else 0
    problems = check()
    if not problems:
        print("refresh check: data looks healthy")
        return 0
    text = ("⚠️ **Tonight's wiki scrape looks wrong, so it was NOT published.** The bots keep yesterday's data.\n"
            + "\n".join(f"• {p}" for p in problems)
            + "\n\nLook at `nightly-refresh.log` in mnm-quests. The wiki may have changed its layout again.")
    print("refresh check FAILED:\n" + "\n".join(problems))
    err = dm(text)
    print("alert DM failed: " + err if err else "alert DM sent")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
