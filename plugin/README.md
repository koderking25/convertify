# Convertify as a plugin

The same Convertify window, in a plugin slot, in whatever you are working in. Audio passes
through untouched: this is not an effect, it is somewhere to put the thing you wanted anyway.

Built as **AU**, **VST3** and a **standalone app** from one set of sources.

| | |
|---|---|
| Logic Pro, GarageBand, Ableton, Studio One, Cubase, Bitwig, Reaper | AU or VST3 |
| Pro Tools | no (AAX needs Avid's SDK and a signed developer account) |

## What it does, and what it deliberately does not

It carries no downloader, no ffmpeg and no Python. It talks to the engine the Convertify app
already serves on 127.0.0.1:8766, the same one the app's own window uses. If the app is not
running, the plugin starts it and waits; a first ever run takes about a minute while the app
builds its own environment.

That is why the plugin is five megabytes instead of ninety, why it is never a version behind
the app, and why **the Finder still opens with your file picked out** when a conversion
finishes: that happens in the engine, which is a normal process on your Mac, so it works the
same whether you asked from the app, from Reaper, or from a plugin window in Logic.

It cannot put the file on a track. No plugin can, in any DAW: an AU, VST3 or CLAP plugin is
handed blocks of audio to process and the format has no notion that the host even has a track
list. Only a host's own scripting can place a clip, which is what `daw/reaper` does for Reaper.

## Building

    cmake -B build -DJUCE_DIR=/path/to/JUCE -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release -j8

Needs CMake and the macOS Command Line Tools; full Xcode is not required. JUCE 9 brings the
VST3 SDK with it. The build installs into `~/Library/Audio/Plug-Ins/` on its own.

Checked with `auval -v aufx Cvt1 Cvfy`, which is the validation Logic runs before it will load
an Audio Unit, and loaded on a track in Reaper as both AU and VST3.

## Installing it somewhere else

    ~/Library/Audio/Plug-Ins/Components/Convertify.component     (AU: Logic, GarageBand)
    ~/Library/Audio/Plug-Ins/VST3/Convertify.vst3                (VST3: everything else)

Both are in the release as `Convertify-plugins.zip`. Convertify itself has to be installed too,
since the plugin is the window and the app does the work.
