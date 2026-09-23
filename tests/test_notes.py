"""notes.txt handling: block placement, old-marker migration, /note corrections."""
from datetime import datetime as dt

import mnm_quests as mq
from conftest import journal_line, make_char, write_journal


def test_read_notes_missing_file(game):
    assert mq.read_notes() == ("", "", "")


def test_write_notes_fresh_file(game):
    block = f"{mq.BLOCK_START}\nupdated Sep 24 12:00\n- (abc123) Bring me five bone chips\n{mq.BLOCK_END}"
    assert mq.write_notes(block, pre="my own note")
    text = mq.NOTES_FILE.read_text("utf-8")
    assert text.startswith("my own note\n\n")
    assert "abc123" in text
    pre, cur, post = mq.read_notes()
    assert pre.startswith("my own note")
    assert "abc123" in cur
    assert post == "\n"  # the newline after the block


def test_write_notes_identical_block_is_noop(game):
    block = mq.render_notes_block({}, None)
    assert mq.write_notes(block) is True
    assert mq.write_notes(block) is False  # unchanged -> no rewrite


def test_write_notes_stamp_change_does_not_trigger_rewrite(game):
    block = f"{mq.BLOCK_START}\nupdated Sep 24 12:00\n\n== Tavi (0 open) ==\n{mq.BLOCK_END}"
    assert mq.write_notes(block, pre="hello")
    stamped = f"{mq.BLOCK_START}\nupdated Sep 24 13:00\n\n== Tavi (0 open) ==\n{mq.BLOCK_END}"
    # Second pass with no pre/post: the live file's user text is used for the comparison.
    assert mq.write_notes(stamped) is False


def test_old_markers_replaced(game):
    old = ("user text\n===== QUEST TRACKER (auto-generated, edits below are overwritten) =====\n"
           "old block\n===== END QUEST TRACKER =====\nafter")
    mq.NOTES_FILE.write_text(old.replace("\n", "\r\n"), encoding="utf-8")  # game used CRLF historically
    pre, cur, post = mq.read_notes()
    assert pre == "user text\n"
    assert "old block" in cur
    assert post == "\nafter"
    # A fresh write replaces the old block between the new markers.
    mq.write_notes(f"{mq.BLOCK_START}\nnew\n{mq.BLOCK_END}")
    pre, cur, post = mq.read_notes()
    assert "new" in cur and "old block" not in cur
    assert pre.strip() == "user text" and post.strip() == "after"


def test_player_text_survives_around_block(game):
    mq.NOTES_FILE.write_text(f"top notes\n\n{mq.BLOCK_START}\nx\n{mq.BLOCK_END}\nbottom notes",
                             encoding="utf-8")
    pre, _, post = mq.read_notes()
    assert pre.strip() == "top notes"
    assert post.strip() == "bottom notes"


def _write(pre: str, block: str = "") -> None:
    text = (pre + "\n\n" if pre else "") + block
    mq.NOTES_FILE.write_text(text, encoding="utf-8")


def test_corrections_done_hide_undo_stripped(game):
    _write("undo abc123\ndone abc123\nhide def456\nkeep this line")
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    app_cmds = mq.apply_note_corrections(state)
    assert app_cmds == []
    assert state["done"] == {"abc123": mq.datetime.now().strftime("%Y-%m-%d")}
    assert "def456" in state["hidden"]
    assert "abc123" not in state["reopened"]  # done clears the earlier undo
    pre, _, __ = mq.read_notes()
    assert "done abc123" not in pre and "hide def456" not in pre and "undo abc123" not in pre
    assert "keep this line" in pre


def test_corrections_got_ungot(game):
    _write("got abc123 3\nungot def456 2")
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    mq.apply_note_corrections(state)
    assert state["got"] == {"abc123": [3]}  # ungot of an unmarked sub-item is a no-op


def test_app_commands_returned_and_stripped(game):
    _write("/mobetta reload\n/mbq help\nplain line")
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    app_cmds = mq.apply_note_corrections(state)
    assert app_cmds == [("reload", None), ("help", None)]
    pre, _, __ = mq.read_notes()
    assert "/mobetta" not in pre and "/mbq" not in pre
    assert "plain line" in pre


def test_block_x_marks_apply_done(game):
    block = f"{mq.BLOCK_START}\n- (abc123) Bring me five bone chips x\n{mq.BLOCK_END}"
    _write("", block)
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    mq.apply_note_corrections(state)
    assert "abc123" in state["done"]


def test_block_h_mark_hides(game):
    block = f"{mq.BLOCK_START}\nh (def456)\n{mq.BLOCK_END}"
    _write("", block)
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    mq.apply_note_corrections(state)
    assert "def456" in state["hidden"]


def test_no_corrections_keeps_state_untouched(game):
    _write("nothing to see here")
    state = {"done": {}, "hidden": [], "reopened": [], "got": {}}
    mq.apply_note_corrections(state)
    assert state == {"done": {}, "hidden": [], "reopened": [], "got": {}}
    assert not mq.STATE_FILE.exists()


def test_sub_item_state_applied_to_items(game, soon):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Collect a fire beetle eye, a rat tail, and a snake fang."),
    ])
    tasks = mq.parse_char(char, {"done": {}, "hidden": [], "reopened": [], "got": {}})[0].tasks
    tid = tasks[0].id
    state = {"done": {}, "hidden": [], "reopened": [], "got": {tid: [2]}}
    tasks = mq.parse_char(char, state)[0].tasks
    assert [i.manual for i in tasks[0].items] == [False, True, False]
    assert [i.counter for i in tasks[0].items] == ["0/1", "got it", "0/1"]


def test_write_unmatched(game):
    npc = mq.Npc("Tavi", "Merchant", dt(2026, 9, 1, 12, 0, 0),
                 unmatched=[(dt(2026, 9, 1, 12, 0, 0), "The mill has been quiet since the flood.")])
    mq.write_unmatched({"Tavi": [npc]})
    text = mq.UNMATCHED_FILE.read_text("utf-8")
    assert "## Tavi" in text and "flood" in text


def test_write_unmatched_failure_is_silent(game, monkeypatch):
    monkeypatch.setattr(mq, "UNMATCHED_FILE", game)  # a directory -> OSError on write
    mq.write_unmatched({})  # must not raise
    assert True