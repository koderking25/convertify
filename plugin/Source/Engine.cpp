#include "Engine.h"

namespace convertify
{
    juce::String pageUrl()
    {
        return "http://127.0.0.1:" + juce::String (port) + "/";
    }

    static juce::String get (const juce::String& path, int timeoutMs)
    {
        juce::URL url ("http://127.0.0.1:" + juce::String (port) + path);
        std::unique_ptr<juce::InputStream> stream (
            url.createInputStream (juce::URL::InputStreamOptions (juce::URL::ParameterHandling::inAddress)
                                       .withConnectionTimeoutMs (timeoutMs)));
        if (stream == nullptr)
            return {};
        return stream->readEntireStreamAsString();
    }

    bool engineIsAnswering()
    {
        //  Not just "something is listening": another program could have the port. The reply
        //  has to look like Convertify's own.
        auto reply = get ("/api/status", 1500);
        return reply.contains ("\"version\"") && reply.contains ("\"formats\"");
    }

    juce::File findTheApp()
    {
        const juce::File places[] = {
            juce::File ("/Applications/Convertify.app"),
            juce::File::getSpecialLocation (juce::File::userHomeDirectory)
                .getChildFile ("Applications/Convertify.app"),
        };
        for (auto& p : places)
            if (p.exists())
                return p;
        return {};
    }

    bool askTheAppToStart()
    {
        auto app = findTheApp();
        if (! app.exists())
            return false;

        //  -g so it opens behind: you asked for this from inside a DAW, and having a window
        //  jump in front of the session you are working on is not a kindness.
        juce::ChildProcess open;
        juce::StringArray command { "/usr/bin/open", "-g", app.getFullPathName() };
        return open.start (command);
    }

    bool waitForTheEngine (int secondsToWait, const std::function<bool()>& giveUp)
    {
        const auto until = juce::Time::getMillisecondCounter() + (juce::uint32) (secondsToWait * 1000);
        while (juce::Time::getMillisecondCounter() < until)
        {
            if (giveUp != nullptr && giveUp())
                return false;
            if (engineIsAnswering())
                return true;
            juce::Thread::sleep (500);
        }
        return false;
    }
}
