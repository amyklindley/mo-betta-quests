"""Journal parsing: sentence splitting, zone placement, task extraction, state."""
from datetime import datetime, timedelta

import pytest

import mnm_quests as mq
from conftest import journal_line, make_char, write_journal, write_ledger


def st():
    """A full state dict, as load_state() would produce."""
    return {"done": {}, "hidden": [], "reopened": [], "got": {}}


def test_split_sentences_strips_tags():
    assert mq.split_sentences("Hello <i>there</i>. What is your name?") == ["Hello there.", "What is your name?"]


def test_split_sentences_capital_follows_punctuation():
    assert mq.split_sentences("Go east. The mill is burning! Come quickly.") == \
        ["Go east.", "The mill is burning!", "Come quickly."]


def test_zone_at_matches_nearest_within_45min(now):
    t = now
    tl = [(t - timedelta(minutes=10), "Night Harbor East"), (t + timedelta(minutes=30), "Fallen Pass")]
    assert mq.zone_at(tl, t) == "Night Harbor East"
    assert mq.zone_at([], t) == ""
    assert mq.zone_at([(t - timedelta(hours=2), "Shaded Dunes")], t) == ""


def test_pretty_zone():
    assert mq.pretty_zone("nightharbore") == "Night Harbor East"
    assert mq.pretty_zone("sunken_grotto") == "Sunken Grotto"
    assert mq.pretty_zone("unknown") == "Unknown"


def test_parse_char_creates_task(game, now, soon):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [{"act": "act_13", "when": soon, "qty": 1, "name": "Stone", "zone": "nightharbore"}])
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Well met, traveler. I need you to take this tunic to Sedgewick."),
    ])
    npcs = mq.parse_char(char, st())
    assert len(npcs) == 1
    npc = npcs[0]
    assert npc.name == "Merchant" and npc.char == "Tavi"
    assert npc.zone == "Night Harbor East"
    assert len(npc.tasks) == 1
    t = npc.tasks[0]
    assert t.status == "open"
    assert t.text == "I need you to take this tunic to Sedgewick."
    assert len(t.id) == 6
    assert t.when == soon.replace(microsecond=0)  # journal timestamps are second-precision


def test_task_ids_stable_across_parses(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant",
                  [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    a = mq.parse_char(char, st())[0].tasks[0].id
    b = mq.parse_char(char, st())[0].tasks[0].id
    assert a == b


def test_noise_line_not_a_task_nor_unmatched(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [journal_line("Merchant", soon, "says Well met, traveler.")])
    npcs = mq.parse_char(char, st())
    assert npcs == []  # no tasks, no turn-ins, no unmatched (too short), no gifts


def test_unmatched_long_non_task_sentence(game, now):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", now - timedelta(days=1),
                     "says The mill has been quiet since the flood took the west road."),
    ])
    npc = mq.parse_char(char, st())[0]
    assert len(npc.unmatched) == 1
    assert "flood" in npc.unmatched[0][1]


def test_unmatched_older_than_7_days_excluded(game):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", datetime(2020, 1, 1, 12, 0, 0),
                     "says The mill has been quiet since the flood took the west road."),
    ])
    assert mq.parse_char(char, st()) == []


def test_turn_in_marks_earlier_tasks_likely_done(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Bring me the tonic when it is ready."),
        journal_line("Merchant", soon + timedelta(minutes=5),
                     "says Thank you for your help, the tonic will do nicely."),
    ])
    parsed = mq.parse_char(char, st())
    assert parsed[0].tasks[0].status == "likely-done"
    assert len(parsed[0].turn_ins) == 1


def test_request_with_reward_language_is_a_task_not_a_turn_in(game, soon):
    # "...as promised" is DONE-cue language; a fetch request ending with it must
    # stay a task and must not mark earlier quests as likely-done.
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Bring me the tonic when it is ready."),
        journal_line("Merchant", soon + timedelta(minutes=3),
                     "says Bring me three of their honey drops and I will bake you a cake as promised."),
    ])
    npc = mq.parse_char(char, st())[0]
    assert len(npc.tasks) == 2
    assert all(t.status == "open" for t in npc.tasks)
    assert npc.turn_ins == []  # no false thank-you
    assert any("honey drops" in t.text for t in npc.tasks)


def test_reopened_task_stays_open_after_turn_in(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Bring me the tonic when it is ready."),
        journal_line("Merchant", soon + timedelta(minutes=5),
                     "says Thank you for your help, the tonic will do nicely."),
    ])
    tid = mq.parse_char(char, st())[0].tasks[0].id
    state = st()
    state["reopened"] = [tid]
    assert mq.parse_char(char, state)[0].tasks[0].status == "open"


def test_hidden_and_done_state(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Bring me five of their bone chips for the ward."),
        journal_line("Merchant", soon + timedelta(minutes=1),
                     "says Take this coin to the smith and have him forge a new key."),
    ])
    tasks = mq.parse_char(char, st())[0].tasks
    assert len(tasks) == 2
    state = st()
    state["done"] = {tasks[0].id: "2026-09-01"}
    state["hidden"] = [tasks[1].id]
    by_id = {t.id: t.status for t in mq.parse_char(char, state)[0].tasks}
    assert by_id[tasks[0].id] == "done"
    assert by_id[tasks[1].id] == "hidden"


def test_dangling_task_borrows_previous_statement(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon,
                     "says The crates are at the north dock. Take this manifest and head back down."),
    ])
    t = mq.parse_char(char, st())[0].tasks[0]
    assert t.text == "The crates are at the north dock. Take this manifest and head back down."


def test_task_after_task_keeps_own_text(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon,
                     "says I need you to clear the cellar. Take this tunic to Sedgewick afterwards."),
    ])
    texts = [t.text for t in mq.parse_char(char, st())[0].tasks]
    assert "I need you to clear the cellar." in texts
    assert "Take this tunic to Sedgewick afterwards." in texts


def test_continuation_after_colon(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Collect the following supplies for the ritual:"),
        journal_line("Merchant", soon + timedelta(minutes=1),
                     "says ...a natural light source, butchered from a proximal creature..."),
    ])
    t = mq.parse_char(char, st())[0].tasks[0]
    assert "natural light source" in t.text


def test_give_emote_captures_item(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "places a small key on the bar"),
    ])
    npc = mq.parse_char(char, st())[0]
    # Journal timestamps are second-precision; the fixture carries microseconds.
    assert npc.given == [(soon.replace(microsecond=0), "a small key")]


def test_give_emote_not_an_item(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "gives you a generous nod"),
    ])
    assert mq.parse_char(char, st()) == []


def test_list_answer_merged_into_task(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_ledger(char, [{"act": "act_13", "when": soon, "qty": 2, "name": "Rat Meat"}])
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Here's what I need from you, friend."),
        journal_line("Merchant", soon + timedelta(minutes=2),
                     "says Meat from the rats, eggs from the snakes, and legs from the beetles."),
    ])
    tasks = mq.parse_char(char, st())[0].tasks
    merged = [t for t in tasks if "Meat from the rats" in t.text]
    assert len(merged) == 1
    # The appended list also fed the loot counters.
    assert any(i.name == "Rat Meat" and i.have == 2 for i in merged[0].items)


def test_parse_all_filters_char(game, soon):
    a = make_char(game, "beta1", "Tavi")
    b = make_char(game, "beta1", "Ulric")
    write_journal(a, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    write_journal(b, "Guildmaster", [journal_line("Guildmaster", soon, "says I need you to sweep the great hall.")])
    all_chars = mq.parse_all(st())
    assert set(all_chars) == {"Tavi", "Ulric"}
    assert set(mq.parse_all(st(), only_char="ulric")) == {"Ulric"}


def test_parse_all_missing_root_raises(game, monkeypatch):
    monkeypatch.setattr(mq, "SERVER", "nonexistent")
    with pytest.raises(mq.GameDataNotFoundError, match="Game data folder not found"):
        mq.parse_all(st())


def test_parse_char_missing_journal_is_empty(game):
    assert mq.parse_char(make_char(game, "beta1", "Tavi"), st()) == []


def test_embedded_timestamp_split(game, soon):
    # The game occasionally glues two entries onto one line.
    char = make_char(game, "beta1", "Tavi")
    glued = (journal_line("Merchant", soon, "says Bring me five bone chips for the ward.")
             + journal_line("Merchant", soon + timedelta(minutes=1), "says I need you to sweep the great hall."))
    write_journal(char, "Merchant", [glued])
    tasks = mq.parse_char(char, st())[0].tasks
    assert len(tasks) == 2