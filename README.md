# MnM Quests

Quest reminders for Monsters & Memories, built from the game's own journal
files. No addons, no memory reading, nothing injected into the game.

The game writes every NPC line to
`%USERPROFILE%\AppData\LocalLow\Niche Worlds Cult\Monsters and Memories\<server>\<Character>\journal\<NPC>`
and keeps the `/note` window in `...\Monsters and Memories\notes.txt`.
MnM Quests reads the journals, keeps the sentences where an NPC told you to do
something, shows them in a small always-on-top overlay, and appends the same
list to `notes.txt` so it shows up in `/note` in-game. Anything you typed in
`/note` yourself is left alone.

## Install

1. Unzip `MnMQuests-win64.zip` anywhere and run `install.bat`. It copies the
   app to `%LOCALAPPDATA%\MnMQuests`, adds a Start Menu shortcut, asks whether
   to start with Windows, and launches it.
2. Windows SmartScreen will warn the first time because the exe is not
   code-signed: click **More info**, then **Run anyway**.
3. Look for the gold check icon in the system tray. Play; the overlay fills in
   as you talk to NPCs.

`uninstall.bat` (in the install folder) removes everything, and asks whether
to keep your done/hidden marks.

Prefer no installer? Just run `MnMQuests.exe` from anywhere; it keeps its
files next to itself.

## Controlling it

| How | What |
|---|---|
| **Ctrl+Shift+Q** | show / hide the overlay (works while the game has focus, if the game is windowed or borderless) |
| **Tray icon** | left-click toggles the overlay; right-click for reload, start with Windows, log, quit |
| **`/note` in-game** | type `/mnmquest <command>` on its own line above the quest block, then close the window |
| **Run the exe again** | `MnMQuests.exe open`, `hide`, `toggle`, `reload`, `quit` (no argument = open) |

`/mnmquest` commands:

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

## Marking quests done

- **Overlay:** tick the box. The task stays listed, struck through, so a
  mis-click is one more click to undo. It leaves the main list only when you
  hit **hide** or when every task from that NPC is done. Each character has a
  "done & hidden" fold at the bottom with an **undo** per task.
- **In `/note`:** change the leading `-` of a task line to `x` (or `h` to hide
  it), then close the window. Or `/mnmquest done <id>`.

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
  `overlay_pos.json`, `quests.md`, `mnmquests.log` next to the exe.
- Exclusive-fullscreen games cover always-on-top windows. If you never see the
  overlay while playing, switch the game to borderless/windowed, or rely on the
  `/note` block.

## Building from source

```
python -m pip install -r requirements.txt
build.bat
```

Produces `dist\MnMQuests.exe` and `dist\MnMQuests-win64.zip`. To run from
source instead: `python overlay.py`. `mnm_quests.py` is the parser and also a
CLI (`list`, `all`, `write`, `watch`, `done`, `undo`, `hide`); the regexes near
its top decide what counts as a task.
