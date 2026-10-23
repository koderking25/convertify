#pragma once
#include <juce_core/juce_core.h>

/*  Finding, and if need be starting, the Convertify engine.

    The plugin carries no downloader, no ffmpeg and no Python. It talks to the engine the
    Convertify app already serves on 127.0.0.1, which is the same one the app's own window
    uses. That is deliberate: one copy of the machinery, one set of updates, and a plugin
    that stays a few hundred kilobytes instead of ninety megabytes in every DAW you own.  */
namespace convertify
{
    inline constexpr int port = 8766;

    juce::String pageUrl();

    /*  Is something answering on the port, and is it really Convertify?  */
    bool engineIsAnswering();

    /*  Where the app is, or an empty path if it is not installed.  */
    juce::File findTheApp();

    /*  Ask the app to start. Returns false if it is not installed at all.  */
    bool askTheAppToStart();

    /*  Wait, on a background thread, until the engine answers or we give up.
        The first ever launch builds an environment, which takes about a minute.  */
    bool waitForTheEngine (int secondsToWait, const std::function<bool()>& giveUp);
}
