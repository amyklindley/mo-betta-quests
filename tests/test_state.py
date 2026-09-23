"""state.json handling: defaults, roundtrip, done/undo/hide/got semantics."""
import json

import mnm_quests as mq


def test_load_state_defaults(game):
    assert mq.load_state() == {"done": {}, "hidden": [], "reopened": [], "got": {}}


def test_load_state_missing_got_key_backfilled(game):
    mq.STATE_FILE.write_text(json.dumps({"done": {"abc123": "2026-09-01"}}), encoding="utf-8")
    state = mq.load_state()
    assert state["done"] == {"abc123": "2026-09-01"}
    assert state["got"] == {}


def test_save_load_roundtrip(game):
    state = {"done": {"abc123": "2026-09-01"}, "hidden": ["def456"], "reopened": [], "got": {"abc123": [2, 3]}}
    mq.save_state(state)
    assert mq.load_state() == state


def test_done_clears_hidden_and_reopened():
    state = {"done": {}, "hidden": ["abc123"], "reopened": ["abc123"], "got": {}}
    mq._apply(state, "done", "abc123")
    assert state["done"]["abc123"]
    assert "abc123" not in state["hidden"]
    assert "abc123" not in state["reopened"]


def test_undo_clears_done_and_hidden_and_reopens():
    state = {"done": {"abc123": "2026-09-01"}, "hidden": ["abc123"], "reopened": [], "got": {}}
    mq._apply(state, "undo", "abc123")
    assert "abc123" not in state["done"]
    assert "abc123" not in state["hidden"]
    assert "abc123" in state["reopened"]


def test_hide_clears_done_and_reopened():
    state = {"done": {"abc123": "2026-09-01"}, "hidden": [], "reopened": ["abc123"], "got": {}}
    mq._apply(state, "hide", "abc123")
    assert "abc123" not in state["done"]
    assert "abc123" in state["hidden"]
    assert "abc123" not in state["reopened"]


def test_set_got_add_remove():
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    mq.set_got(state, "abc123", 3, True)
    assert state["got"]["abc123"] == [3]
    mq.set_got(state, "abc123", 1, True)
    assert state["got"]["abc123"] == [1, 3]
    mq.set_got(state, "abc123", 3, False)
    assert state["got"]["abc123"] == [1]
    mq.set_got(state, "abc123", 1, False)
    assert state["got"] == {}


def test_apply_unknown_verb_is_noop():
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    mq._apply(state, "bogus", "abc123")
    assert state["done"] == {} and state["hidden"] == [] and state["reopened"] == []