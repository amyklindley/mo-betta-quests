# Mo Betta Quests

Quest reminders for Monsters & Memories, built from the game's own journal
files. No addons, no memory reading, nothing injected into the game.

The game writes every NPC line to
`%USERPROFILE%\AppData\LocalLow\Niche Worlds Cult\Monsters and Memories\<server>\<Character>\journal\<NPC>`
and keeps the `/note` window in `...\Monsters and Memories\notes.txt`.
Mo Betta Quests reads the journals, keeps the sentences where an NPC told you to do
something, shows them in a small always-on-top overlay, and appends the same
list to `notes.txt` so it shows up in `/note` in-game. Anything you typed in
`/note` yourself is left alone.

## Install

1. Unzip `MoBettaQuests-win64.zip` anywhere and run `install.bat`. It copies the
   app to `%LOCALAPPDATA%\MoBettaQuests`, adds a Start Menu shortcut, asks whether
   to start with Windows, and launches it.
2. Windows SmartScreen will warn the first time because the exe is not
   code-signed: click **More info**, then **Run anyway**.
3. Look for the gold check icon in the system tray. Play; the overlay fills in
   as you talk to NPCs.

`uninstall.bat` (in the install folder) removes everything, and asks whether
to keep your done/hidden marks.

Prefer no installer? Just run `MoBettaQuests.exe` from anywhere; it keeps its
files next to itself.

## Controlling it

| How | What |
|---|---|
| **Ctrl+Shift+Q** | show / hide the overlay (works while the game has focus, if the game is windowed or borderless) |
| **Tray icon** | left-click toggles the overlay; right-click for reload, start with Windows, log, quit |
| **`/note` in-game** | type `/mobetta <command>` on its own line above the quest block, then close the window (`/mbq` and `/mnmquest` work too) |
| **Run the exe again** | `MoBettaQuests.exe open`, `hide`, `toggle`, `reload`, `quit` (no argument = open) |

`/mobetta` commands:

```
open | hide | toggle     show / hide the overlay
reload                   rebuild the list right now
done <id>  undo <id>     finish / reopen a task (ids are the 6-character codes)
hide <id>                never show that line again
char <name> | auto       pin the overlay to one character / follow the game
startup on | off         start with Windows
help                     print this list into the note block
quit                     close the app
```

The command line is removed from your notes once it has been applied. Nothing
happens until you close the `/note` window, because that is when the game
saves the file.

## What the overlay shows

A row of character tabs (the one the game is on has a dot; click another to
look at it, click the dotted one to follow the game again), then one card per
quest for that character:

- the quest name, with level and zone under it
- what to do now: the wiki's next step when the quest is known, otherwise the
  newest instruction the NPC gave you
- the items it wants, one line each with a counter
- what to say next, in green, when the next step is a keyword

Click the card's name to unfold it: the NPC's own sentences with a checkbox
and hide button each (click a sentence to see the lines around it), the
reward, anything the NPC handed you, the other NPCs involved, and a link to
the wiki page. **✔ done** on the card marks every open task in it done;
**hide** hides them all. A "done & hidden" fold at the bottom lists everything
you have finished or hidden, with an undo per line.

## Marking quests done

- **Overlay:** ✔ done on the card, or unfold it and tick single sentences. A
  ticked sentence stays listed, struck through, so a mis-click is one more
  click to undo. Each character has a "done & hidden" fold with an **undo** per
  task.
- **In `/note`:** change the leading `-` of a task line to `x` (or `h` to hide
  it), then close the window. Or `/mobetta done <id>`.

## When a quest is missed

The app decides what counts as a task from a phrase library in `phrases.py`:
plain lists of request wording ("I need you to"), task phrases ("bring me",
"fill the bag"), instruction verbs that open a sentence ("Show this coin to"),
and noise to ignore ("take no offense"). If an NPC's instruction was not picked
up, open `unmatched.txt` next to the exe: it lists every NPC sentence from the
last 7 days that was not treated as a task. Send that file (or the missed line)
to whoever maintains the library and the phrasing gets added.

## What else it reads

- **Items NPCs hand you.** Emote lines like "hands you a small key" or "places
  a filthy bag on the bar" show up under the NPC as "gave you: ...", so you
  know which quest item in your bags belongs to whom.
- **Item sub-tasks with counters.** When a task asks for things ("six of their
  legs", "eight bat wings, then a fire beetle eye") each item gets its own line
  under the task with a counter like `2/6`. The count is an estimate of what is
  in your bags, worked out from the game's Ledger: everything that character
  has looted from corpses, minus everything sold or dropped. The game does not
  log hand-ins to NPCs or items bought or crafted, so after you turn a stack in
  the counter stays full until you tick the task. For something you bought or
  were given, click the circle next to the sub-item in the overlay (or type
  `/mobetta got <task id> <sub-item number>` in `/note`) to mark it in hand;
  click again to revert. "Intact" tasks skip loot
  named "broken", and when the NPC names the creature the counter only takes
  that creature's drops. If you ask an NPC for specifics and they answer with a
  list ("meat from the four-legged ones, eggs from the snakes..."), that answer
  is folded into the task and each entry becomes a sub-item with a running
  count, even though the answer had no numbers in it.
- **Turn-in emotes.** "takes the note", "accepts the items", "counting out the
  bat wings" count as completion cues, same as a thank-you line.

## What the wiki adds

The app ships with the walkthroughs of every quest on the community wiki
(`quests.json`, built by `wiki_quests.py`). NPC dialogue in your journal is
matched word for word against those walkthroughs, so under each NPC you get:

- **which quest this is**, with level and zone; click the name to open the wiki page
- **the next step** as the wiki phrases it ("Hand in 5 Bone Chips to Squire Ryland"),
  with the wiki's exact items and a counter each
- **what to say** when the next step is a keyword ("What is your task?")
- **the reward**

When several NPCs belong to one quest, progress is worked out from whichever
conversation is most recent; that NPC shows the full block and the others say
"part of". To refresh the walkthroughs after the wiki changes, run
`python wiki_quests.py` and drop the new `quests.json` next to the exe (a file
next to the exe beats the bundled one).

## How status is decided

- open: the NPC said it and nothing newer suggests it is finished.
- likely done (shown under "done & hidden" as *auto*): the same NPC later said a
  thank-you / reward line. Undo it if the tool guessed wrong.
- done / hidden: your marks, stored in `state.json`.

Turn-ins to a different NPC than the one who asked are not detected; tick the
box or use `done <id>`.

## Notes for the curious

- Only one `notes.txt` exists, shared by all characters. The block shows the
  character you are playing in full (the one whose folder the game wrote to
  most recently) and the others as counts.
- The game reads `notes.txt` when you open `/note` and writes its own copy
  back when you close it. The app re-appends the block a few seconds later if
  the game overwrote it. Your text is never lost.
- Files the app writes: `notes.txt` in the game folder; `state.json`,
  `overlay_pos.json`, `quests.md`, `MoBettaQuests.log` next to the exe.
- Exclusive-fullscreen games cover always-on-top windows. If you never see the
  overlay while playing, switch the game to borderless/windowed, or rely on the
  `/note` block.

## Building from source

```
python -m pip install -r requirements.txt
build.bat
```

Produces `dist\MoBettaQuests.exe` and `dist\MoBettaQuests-win64.zip`. To run from
source instead: `python overlay.py`. A `pip install .` gives you the same tools
as console commands: `mnm-quests` (the parser CLI, pure stdlib, cross-platform),
`mobetta-overlay` (Windows), and `wiki-quests` (re-fetch the bundled quest data
from the community wiki).

`mnm_quests.py` is the parser and also a
CLI (`list`, `all`, `write`, `watch`, `done`, `undo`, `hide`, `got`, `ungot`);
the regexes near its top decide what counts as a task.

To point the tool at a non-default game data folder (moved install, Wine
prefix, backup copy), set `MNM_GAME_DIR` to the `Monsters and Memories` folder;
it wins over the default `%USERPROFILE%` path.

## Testing

The parser and the notes/state logic are pure Python and test without the game:

```
python -m pip install -e ".[dev]"
python -m pytest
```

The suite builds a synthetic game folder (journals, Ledger, `/note` file) in a
temp dir and exercises task extraction, loot matching, note-block rewriting and
the CLI - no Monsters & Memories install needed.

## License

MIT. Use it, fork it, share it. See LICENSE.
