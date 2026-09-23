"""Ledger parsing and loot matching against required items."""
from datetime import datetime, timedelta

import mnm_quests as mq
from conftest import make_char, write_ledger


def test_loot_since_signs_and_quantities(game, now):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [
        {"act": "act_13", "when": now - timedelta(hours=2), "qty": 2, "name": "Bone Chip"},
        {"act": "act_27", "when": now - timedelta(hours=1), "qty": 1, "name": "Bone Chip"},
        {"act": "act_24", "when": now - timedelta(minutes=30), "qty": 1, "name": "Bone Chip"},  # sold
        {"act": "act_11", "when": now - timedelta(minutes=10), "qty": 1, "name": "Bone Chip"},  # dropped
    ])
    loot = mq.loot_since(char, now - timedelta(days=1))
    assert sorted(q for _, _, q, _ in loot) == [-1, -1, 1, 2]
    assert all(n == "Bone Chip" for _, n, _, _ in loot)


def test_loot_since_filters_unknown_acts_and_bad_rows(game, now):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [
        {"act": "act_99", "when": now, "qty": 5, "name": "Mystery"},
        {"act": "act_13", "when": now, "qty": 1, "name": "Beetle Leg", "corpse": "a dune scarab"},
    ])
    loot = mq.loot_since(char, mq.LEDGER_EPOCH)
    assert len(loot) == 1
    _, name, qty, corpse = loot[0]
    assert name == "Beetle Leg" and qty == 1 and corpse == "a dune scarab"


def test_loot_since_corrupt_json_skipped(game, now):
    char = make_char(game, "beta1", "Tavi")
    (char / "Ledger").mkdir(parents=True)
    (char / "Ledger" / "garbage.json").write_text("not json", encoding="utf-8")
    assert mq.loot_since(char, mq.LEDGER_EPOCH) == []


def test_loot_since_time_filter(game, now):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [
        {"act": "act_13", "when": now - timedelta(days=3), "qty": 1, "name": "Old Fang"},
        {"act": "act_13", "when": now - timedelta(hours=1), "qty": 1, "name": "New Fang"},
    ])
    loot = mq.loot_since(char, now - timedelta(days=1))
    assert [n for _, n, _, _ in loot] == ["New Fang"]


def _loot(entries):
    t0 = datetime.now()
    return [(t0, name, qty, corpse) for name, qty, corpse in entries]


def test_match_loot_head_noun():
    loot = _loot([("Bone Chip", 3, ""), ("Scarab Leg", 2, "")])
    have, name = mq.match_loot(["bone", "chip"], False, loot)
    assert have == 3 and name == "Bone Chip"


def test_match_loot_modifier_must_match():
    loot = _loot([("Moth Wings", 2, ""), ("Bat Wings", 1, "")])
    have, name = mq.match_loot(["bat", "wing"], False, loot)
    assert have == 1 and name == "Bat Wings"


def test_match_loot_corpse_name_counts():
    loot = _loot([("Scarab Eye", 1, "a dune scarab"), ("Scarab Eye", 3, "a crypt scarab")])
    have, name = mq.match_loot(["dune", "scarab", "eye"], False, loot)
    assert have == 1 and name == "Scarab Eye"


def test_match_loot_intact_filter():
    loot = _loot([("Broken Bone Chip", 2, ""), ("Intact Bone Chip", 1, "")])
    have, _ = mq.match_loot(["bone", "chip"], True, loot)
    assert have == 1
    have, _ = mq.match_loot(["bone", "chip"], False, loot)
    assert have == 3


def test_match_loot_sales_subtracted():
    loot = _loot([("Bone Chip", 4, ""), ("Bone Chip", -3, "")])
    have, name = mq.match_loot(["bone", "chip"], False, loot)
    assert have == 1 and name == "Bone Chip"


def test_match_loot_text_words_prefer_named_creature():
    loot = _loot([("Grain Beetle Leg", 2, ""), ("Scarab Leg", 1, "")])
    have, name = mq.match_loot(["beetle", "leg"], False, loot,
                               text_words={"grain", "beetle", "leg", "mill"})
    assert have == 2 and name == "Grain Beetle Leg"
    # Without the text hint, "beetle" still filters out scarab legs...
    have, name = mq.match_loot(["beetle", "leg"], False, loot)
    assert have == 2 and name == "Grain Beetle Leg"
    # ...but a bare head noun counts every kind of leg together.
    have, name = mq.match_loot(["leg"], False, loot)
    assert have == 3 and name == ""


def test_match_loot_no_candidates():
    assert mq.match_loot(["bone", "chip"], False, []) == (0, "")


def test_task_items_names(game, now):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [{"act": "act_13", "when": now - timedelta(hours=1), "qty": 3, "name": "Bone Chip"}])
    loot = mq.loot_since(char, mq.LEDGER_EPOCH)
    items = mq.task_items("Bring me five of their bone chips and I will pay you well.", loot)
    assert len(items) == 1
    it = items[0]
    assert it.name == "Bone Chip" and it.want == 5 and it.have == 3
    assert it.counter == "3/5" and not it.done


def test_task_items_uses_phrase_when_no_loot_seen():
    items = mq.task_items("Bring me five of their bone chips.", [])
    assert items[0].name == "bone chips"
    assert items[0].counter == "0/5"


def test_task_items_intact_prefix():
    items = mq.task_items("Bring me five intact bone chips for the shrine.", [])
    assert items[0].name == "intact bone chips"


def test_task_items_vague_scope_keeps_phrase(game, now):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [
        {"act": "act_13", "when": now - timedelta(hours=1), "qty": 2, "name": "Boar Meat"},
    ])
    loot = mq.loot_since(char, mq.LEDGER_EPOCH)
    items = mq.task_items("Meat from the four-legged ones, eggs from the snakes, and legs from the beetles.", loot)
    vague = items[0]
    # Display keeps the NPC's wording; "Boar Meat" still counts by head noun.
    assert vague.name == "meat from the four-legged ones"
    assert vague.have == 2


def test_loot_progress():
    loot = _loot([("Bone Chip", 4, "")])
    assert mq.loot_progress("Bring me six of their bone chips.", loot) == "4/6"
    assert mq.loot_progress("Bring me six of their bone chips.", _loot([("Bone Chip", 9, "")])) == "6/6"
    assert mq.loot_progress("Speak with the harbormaster about the shipment.", loot) == ""