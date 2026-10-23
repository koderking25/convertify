# Convertify

**[koderking25.github.io/convertify](https://koderking25.github.io/convertify/)** — downloads, and
what it does, with rather more jokes than this file.

A small Mac app that turns a YouTube link into a file you can keep: MP3, M4A, WAV, FLAC, AAC,
or MIDI. Search by name or paste a link, pick a flavour, press the green button. It saves to
Downloads unless you tell it otherwise, and it opens the folder with your file already picked
out, so there is no hunting.

Convertify is Midify's cousin. Midify listens to music and writes the notes down; Convertify
just gets you the audio. MIDI is the one thing it cannot do alone: it hands that job to Midify
if Midify is installed, because the listening takes 750 MB of models that Convertify has no
business carrying.

## As a plugin

It is also an AU and a VST3, so it opens in a plugin slot in Logic, Reaper, Ableton and the rest.
`plugin/` builds it, `mac/make_installer.py` makes the installer that puts both where DAWs look,
and `daw/reaper` is a script that puts the finished file straight onto a Reaper track.

## Running it from the source

    uv venv --python 3.11 .venv
    uv pip install --python .venv/bin/python -r requirements.txt
    .venv/bin/python convertify/window.py

The engine on its own, without a window, is `convertify/engine.py`; it serves the page on
127.0.0.1:8766.

## Building the app

    .venv/bin/python mac/build.py

That writes `mac/build/Convertify.app`, signs it, and checks the bundle is actually complete
before it says so. The app sets itself up on first run: it builds its own environment in
`~/Library/Application Support/Convertify` rather than needing anything installed first.

## Tests

    for t in tests/test_*.py; do .venv/bin/python "$t"; done

They do not touch the network. The one that converts a whole song stands the download in for
a tone file with a known length, so the test can check the result really is five seconds long
rather than trusting that the code meant well.

## What lives where

    convertify/     the engine, the window, and the page
    shared/         the parts Midify also has: the downloader, the updater, flash drives
    mac/            building the app and drawing its icon
    tests/

`shared/` started as copies of Midify's own files. They are Convertify's now: a fix made here
does not reach Midify, and the other way round, so anything important needs doing in both.

## Updates

The app asks this repository for its newest release every half hour and when you bring it back
to the front, and offers to install it. Releases before 1.4.0 were published in the Midify
repository with a `convertify-v` prefix, which is why 1.4.0 exists in both places: it is the
one that moves an installed copy across to this repository.
