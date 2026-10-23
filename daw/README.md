# Convertify in a DAW

## Reaper: yes, and it is here

`reaper/Convertify_Drop_YouTube_Audio_On_A_Track.lua` asks for a song name or a YouTube link,
waits while Convertify converts it, and puts the result on a new track. It defaults to WAV,
because a DAW should not have to decode anything and the import is then exact.

Install it by copying the file into

    ~/Library/Application Support/REAPER/Scripts/

then in Reaper: Actions > Show action list > New action > Load ReaScript. Give it a keyboard
shortcut and it is two keystrokes from idea to audio on a track.

Convertify has to be running. The script talks to the engine the app already serves on
127.0.0.1:8766, which is the same engine its own window uses, so there is nothing extra to
install and nothing that can fall out of step with the app.

It never blocks Reaper. Waiting happens through `defer`, so playback, the mouse and everything
else carry on while the download runs, and the status line shows what is happening.

### Testing it

    lua test_parsing.lua                  # no network, no Reaper
    lua test_against_the_real_engine.lua  # Convertify must be open; converts one short video

The second one stands in for everything Reaper provides and runs the real script against the
real app, so the only thing not actually exercised is `InsertMedia` itself.

## Logic Pro: no, and not because nobody has tried

Logic has no way to let anything else put a file on a track.

- It ships no AppleScript dictionary. `NSAppleScriptEnabled` is true in its Info.plist, but
  there is no `.sdef`, so all it understands is the standard open/quit/activate suite. Nothing
  about tracks, regions, or importing.
- Scripter, its scripting plugin, is MIDI only. It sees and makes MIDI events in real time. It
  cannot read a file or create a region.
- A plugin cannot do it either, in Logic or anywhere else. An AU, VST or CLAP plugin is handed
  blocks of audio to process. The format has no idea the host even has a track list, let alone
  a way to add something to it. This is why "a plugin that works in any DAW and drops the audio
  on a track" does not exist from anyone: the thing it would need is not part of what a plugin
  is.

What does work in Logic today: Convertify saves where you tell it, so point it at a folder and
drag from there, or add that folder to Logic's own file browser (Browsers > All Files) and drag
it in without leaving Logic. One drag, and it is sample accurate.

## Other DAWs

The dividing line is whether the host exposes its own scripting, not whether it takes plugins.
Reaper does, fully, which is why this works there. Bitwig's controller API and Ableton's
Max for Live are built for control surfaces and devices rather than for importing files, so
neither gives a clean version of this. Pro Tools and Studio One have nothing public for it.
