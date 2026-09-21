# mnm-quests

Quest reminders for Monsters & Memories, built from the game's own journal files.

## Install (no Python needed)

1. Download `MnMQuests.exe` from the latest release and put it in any folder
   (it writes two small files next to itself: `state.json`, `overlay_pos.json`).
2. Double-click it. Windows SmartScreen will warn the first time because the
   file is not code-signed: click **More info**, then **Run anyway**.
3. Play. The overlay lists your open quests, and the game's `/note` window
   gets a quest block appended below your own notes.

It reads only the game's journal files under
`%USERPROFILE%\AppData\LocalLow\Niche Worlds Cult\Monsters and Memories`
and writes only `notes.txt` in that folder plus its own two files. No network,
no game memory access, nothing injected into the game.

To run from source instead: install Python 3.12+, then `python overlay.py`.
To rebuild the exe: `build.bat`.

The game writes every NPC line to
`%USERPROFILE%\AppData\LocalLow\Niche Worlds Cult\Monsters and Memories\beta1\<Character>\journal\<NPC>`
and keeps the `/note` window in `...\Monsters and Memories\notes.txt`.
This script reads the journals, keeps the sentences where an NPC told you to do
something, and appends a quest block to `notes.txt` so it shows up in `/note`
in-game. Anything you typed above the block is left alone.

There is only one `notes.txt`, shared by every character (that is how the game
does it). The block therefore shows the character you are currently playing in
full and collapses the others to a count. "Currently playing" means the
character whose folder the game wrote to most recently. Override it with
`python mnm_quests.py write Denvan`.

## How the game treats notes.txt (tested 2026-09-21)

- The game reads `notes.txt` from disk when you open `/note`, so an update shows
  up without relaunching.
- When you close `/note` the game writes its in-memory copy back, which throws
  away any update made while the window was open. Your typed text is never
  lost; the watcher just re-appends the block a few seconds later, and you see
  the fresh one next time you open `/note`.

## Marking quests done

Three ways, pick whichever is handy:

1. **Inside the game's `/note` window.** Change the leading `-` of a task line
   to `x` (or `h` to hide a false positive), then close the window. You can also
   type `done 8c38db`, `hide 8c38db` or `undo 8c38db` on its own line anywhere in
   your own notes; the line is applied and removed. Needs the watcher or the
   overlay running.
2. **The overlay.** `overlay.bat` opens a small always-on-top window with a
   checkbox per task and a hide button. Every character is a section; click a
   character's header to fold or unfold it. The character you are playing
   unfolds automatically when the game switches. Drag the window by its title
   bar, `–` collapses the whole thing, `×` closes it. It also keeps notes.txt current, so you do not need the
   watcher while it is open. Works when the game is windowed or borderless; in
   exclusive fullscreen you will only see it after alt-tab.
3. **Command line / Claude.** `python mnm_quests.py done 8c38db`, or just tell
   Claude who you turned it in to.

## Use

```bat
overlay.bat             on-screen checklist + keeps notes.txt current
update-notes.bat        rebuild notes.txt + quests.md once
watch-notes.bat         keep rebuilding while you play, no window (checks every 20 s)
python mnm_quests.py list            open quests, all characters
python mnm_quests.py list Moirin     one character
python mnm_quests.py all             include done / likely-done / hidden
python mnm_quests.py done 485bbd     mark a task finished
python mnm_quests.py undo 485bbd     reopen it
python mnm_quests.py hide f63960     it was never a quest, stop showing it
```

Task ids are the 6-character codes shown next to each line.

## How status is decided

- `[ ]` open: the NPC said it and nothing newer suggests it is finished.
- `[~]` likely done: the same NPC later said a thank-you / well-done line.
- `[x]` done: you marked it with `done`. Stored in `state.json`.
- `[-]` hidden: you marked it with `hide`.

Turn-ins to a different NPC are not detected automatically; use `done`.

## Files

- `mnm_quests.py`: the tool. Regexes near the top decide what counts as a task.
- `state.json`: your done / hidden marks.
- `quests.md`: full markdown dump, handy for Claude to read.
