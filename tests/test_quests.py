"""Wiki quest layer (identify_quest / quest_state / build_cards / resolve_quests).

Data-driven against the bundled quests.json, so the whole layer is exercised
with the same walkthroughs the app ships - no network, no game install.
"""
from datetime import datetime, timedelta

import mnm_quests as mq

T0 = datetime(2026, 9, 1, 12, 0, 0)
FAMISHED = "I'm famished! What I wouldn't do for a sweet treat right about now."


def quest_index(title: str) -> int:
    for i, q in enumerate(mq.load_quests()["quests"]):
        if q["title"] == title:
            return i
    raise AssertionError(f"quest not in quests.json: {title}")


def test_load_quests_structure():
    db = mq.load_quests()
    assert len(db["quests"]) >= 100
    assert set(db) == {"quests", "exact", "prefix"}
    assert db["exact"] and db["prefix"]  # indexes built at load


def test_match_wiki_line_exact_and_miss():
    assert mq.match_wiki_line(FAMISHED)  # one or more (quest index, line n) hits
    assert mq.match_wiki_line("This is not a line from any wiki page.") == []


def test_identify_quest_from_dialogue():
    hit = mq.identify_quest("Chef Violyn", [(T0, [FAMISHED])])
    assert hit is not None
    assert hit["title"] == "A Sweet Treat"
    assert hit["by_name"] is False
    assert hit["qi"] == quest_index("A Sweet Treat")
    assert hit["matched_lines"] >= 1


def test_identify_quest_unknown_returns_none():
    assert mq.identify_quest("Somebody Nobody", [(T0, ["The weather has been pleasant lately, would you agree?"])]) is None


def test_quest_state_progression():
    qi = quest_index("A Winged Terror")
    early = mq.quest_state(qi, 0)
    assert early["title"] == "A Winged Terror"
    assert early["next_step"]  # first step exists
    assert early["done"] is False
    lines = mq.load_quests()["quests"][qi]["lines"]
    last = max(l["n"] for l in lines)
    done = mq.quest_state(qi, last)
    assert done["done"] is True and done["next_step"] == ""


def test_quest_state_step_items():
    qi = quest_index("A Winged Terror")
    st = mq.quest_state(qi, 8)  # line 9 asks for Night Terror's Wing
    assert st["next_items"] == [{"name": "Night Terror's Wing", "qty": 1}]


def test_build_cards_groups_and_titles():
    chef = mq.Npc("Tavi", "Chef Violyn", T0, quest=mq.identify_quest("Chef Violyn", [(T0, [FAMISHED])]))
    guard = mq.Npc("Tavi", "Guard Halfsies", T0 - timedelta(minutes=5))
    cards = mq.build_cards([chef, guard])
    assert len(cards) == 2
    wiki, lone = cards
    assert wiki.key == "A Sweet Treat"
    assert wiki.title == "A Sweet Treat"
    assert wiki.url.startswith("https://")
    assert wiki.by_name is False
    assert wiki.open  # a next step exists
    assert wiki.npcs == [chef]
    assert lone.key == "npc:Guard Halfsies"
    assert lone.title == "Guard Halfsies"


def test_build_cards_open_tasks_and_items():
    chef = mq.Npc("Tavi", "Chef Violyn", T0, quest=mq.identify_quest("Chef Violyn", [(T0, [FAMISHED])]))
    chef.tasks = [mq.Task("abc123", "Tavi", "Chef Violyn", T0, FAMISHED)]
    card = mq.build_cards([chef])[0]
    assert card.open_tasks == chef.tasks
    assert card.now  # wiki next step outranks the task text
    assert card.last_seen == T0


def test_resolve_quests_picks_lead_and_summarises_others():
    chef_q = mq.identify_quest("Chef Violyn", [(T0, [FAMISHED])])
    guard_q = mq.identify_quest("Guard Halfsies", [(T0 - timedelta(hours=1), [FAMISHED])])
    chef = mq.Npc("Tavi", "Chef Violyn", T0, quest=chef_q)
    guard = mq.Npc("Tavi", "Guard Halfsies", T0 - timedelta(hours=1), quest=guard_q)
    mq.resolve_quests([guard, chef], mq.Path("/nonexistent"), None)
    assert guard.quest is not None and chef.quest is not None
    assert guard.quest["summary_only"] is True
    assert guard.quest["lead"] == "Chef Violyn"
    assert guard.quest_items == []
    assert chef.quest["summary_only"] is False
    assert chef.quest_items == []  # next_items exists but no Ledger loot to count


def test_resolve_quests_no_quest_attr_is_noop():
    npc = mq.Npc("Tavi", "Stranger", T0)
    mq.resolve_quests([npc], mq.Path("/nonexistent"), None)  # must not raise
    assert npc.quest is None


def test_short_truncation():
    assert mq.short("Short text.") == "Short text."
    long_text = "This is a very long sentence indeed, far beyond the configured limit of one hundred seventy characters, " \
                "and it keeps going past every reasonable boundary until it must be cut."
    cut = mq.short(long_text)
    assert len(cut) <= 173
    assert cut.endswith("...")
    assert mq.short(long_text, limit=10).endswith("...")


def test_render_md_shows_quest_link():
    chef = mq.Npc("Tavi", "Chef Violyn", T0, quest=mq.identify_quest("Chef Violyn", [(T0, [FAMISHED])]))
    chef.tasks = [mq.Task("abc123", "Tavi", "Chef Violyn", T0, FAMISHED)]
    md = mq.render_md({"Tavi": [chef]}, show_all=True)
    assert "**quest:** [A Sweet Treat]" in md
    assert "next:" in md


def test_wiki_parse_offline():
    """The wiki scraper's page parser, fed a synthetic walkthrough (no network)."""
    import wiki_quests as wq

    text = (
        "{{Quest\n"
        "| start zone = Night Harbor\n"
        "| quest giver = [[Merchant Bob]]\n"
        "| minimum level = 3\n"
        "| classes = All\n"
        "| related npcs = [[Guard Halfsies]], [[Mierra]]\n"
        "}}\n"
        "== Overview ==\n"
        "The mill needs help.\n"
        "== Walkthrough ==\n"
        "=== Part 1: The Key ===\n"
        ":'''''[[Merchant Bob]] says, \"I need you to pick up the key from the guard room.\"'''''\n"
        ":''You say, \"I'll find the key.\"''\n"
        ":''You receive [[Small Key]] x2 from [[Merchant Bob]].''\n"
        ":''[[Merchant Bob]] says, \"Good. Bring the key back to me before dusk.\"''\n"
        "'''Bring the key back to me before dusk.'''\n"
        "== Rewards ==\n"
        "* 5 gold\n"
        "* 50 experience\n"
    )
    q = wq.parse("The Key", text)
    assert q["title"] == "The Key"
    assert q["giver"] == "Merchant Bob"
    assert q["zone"] == "Night Harbor"
    assert q["min_level"] == "3"
    assert q["related"] == ["Guard Halfsies", "Mierra"]
    assert [l["kind"] for l in q["lines"]] == ["npc", "say", "receive", "npc", "step"]
    npc_lines = [l for l in q["lines"] if l["kind"] == "npc"]
    assert npc_lines[0]["npc"] == "Merchant Bob"
    assert "key from the guard room" in npc_lines[0]["text"]
    says = [l for l in q["lines"] if l["kind"] == "say"]
    assert says[0]["text"] == "I'll find the key."
    receives = [l for l in q["lines"] if l["kind"] == "receive"]
    assert receives[0] == {"n": receives[0]["n"], "kind": "receive", "item": "Small Key", "qty": 2,
                           "npc": "Merchant Bob", "part": "Part 1: The Key"}
    steps = [l for l in q["lines"] if l["kind"] == "step"]
    assert steps[0]["text"] == "Bring the key back to me before dusk."
    assert q["rewards"] == ["5 gold", "50 experience"]
    assert "Merchant Bob" in q["npcs"] and "Guard Halfsies" in q["npcs"] and "Mierra" in q["npcs"]