"""CLI dispatch: commands, exits, missing game data."""
import json

import pytest

import mnm_quests as mq
from conftest import journal_line, make_char, write_journal


def test_list_prints_markdown(game, soon, capsys):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    mq.main(["list"])
    out = capsys.readouterr().out
    assert "## Tavi" in out and "Bring me five of their bone chips." in out


def test_list_char_filter(game, soon, capsys):
    a = make_char(game, "beta1", "Tavi")
    b = make_char(game, "beta1", "Ulric")
    write_journal(a, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    write_journal(b, "Guildmaster", [journal_line("Guildmaster", soon, "says I need you to sweep the hall.")])
    mq.main(["list", "ulric"])
    out = capsys.readouterr().out
    assert "## Ulric" in out and "## Tavi" not in out


def test_list_without_game_data_exits_cleanly(game, monkeypatch, capsys):
    monkeypatch.setattr(mq, "GAME_DIR", game / "missing")
    with pytest.raises(SystemExit) as e:
        mq.main(["list"])
    assert "Game data folder not found" in str(e.value)


def test_write_creates_notes_and_md(game, soon, capsys):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    mq.main(["write"])
    assert game.joinpath("notes.txt").exists()
    assert game.joinpath("quests.md").exists()
    assert "wrote 1 open task(s)" in capsys.readouterr().out
    mq.main(["write"])
    assert "already current" in capsys.readouterr().out


def test_done_saves_state_and_rewrites(game, soon, capsys):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    tid = mq.parse_char(char, mq.load_state())[0].tasks[0].id
    mq.main(["done", tid])
    state = json.loads(mq.STATE_FILE.read_text("utf-8"))
    assert tid in state["done"]
    assert "0 open task(s)" in capsys.readouterr().out


def test_got_and_ungot_cli(game, soon, capsys):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [
        journal_line("Merchant", soon, "says Collect a fire beetle eye, a rat tail, and a snake fang."),
    ])
    tid = mq.parse_char(char, mq.load_state())[0].tasks[0].id
    mq.main(["got", tid, "2"])
    state = json.loads(mq.STATE_FILE.read_text("utf-8"))
    assert state["got"][tid] == [2]
    mq.main(["ungot", tid, "2"])
    state = json.loads(mq.STATE_FILE.read_text("utf-8"))
    assert state["got"] == {}


def test_got_requires_two_args(game, capsys):
    with pytest.raises(SystemExit) as e:
        mq.main(["got", "abc123"])
    assert "usage" in str(e.value)


def test_done_requires_args(game, capsys):
    with pytest.raises(SystemExit) as e:
        mq.main(["done"])
    assert "give at least one task id" in str(e.value)


def test_unknown_command_prints_usage(game, capsys):
    with pytest.raises(SystemExit) as e:
        mq.main(["frobnicate"])
    assert "Usage" in str(e.value) or "mnm_quests.py" in str(e.value)


def test_no_args_defaults_to_list(game, soon, capsys):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])
    mq.main([])
    assert "## Tavi" in capsys.readouterr().out


def test_env_override_resolves_game_dir(monkeypatch):
    monkeypatch.delenv("MNM_GAME_DIR", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    assert mq._resolve_game_dir() == mq.Path("") / "AppData/LocalLow/Niche Worlds Cult/Monsters and Memories"
    monkeypatch.setenv("MNM_GAME_DIR", "/tmp/fake-game")
    assert mq._resolve_game_dir() == mq.Path("/tmp/fake-game")


def test_watch_runs_once_when_sleep_raises(game, soon, monkeypatch, capsys):
    char = make_char(game, "beta1", "Tavi")
    write_journal(char, "Merchant", [journal_line("Merchant", soon, "says Bring me five of their bone chips.")])

    def stop(delay):
        raise KeyboardInterrupt

    monkeypatch.setattr(mq.time, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        mq.main(["watch", "0.05"])
    assert "watching" in capsys.readouterr().out
    assert game.joinpath("notes.txt").exists()