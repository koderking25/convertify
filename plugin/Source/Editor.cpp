#include "Editor.h"
#include "Plugin.h"
#include "Engine.h"

/*  Looking for the engine on a thread of its own. Doing it on the message thread would mean a
    DAW frozen solid while a socket times out, and on a first ever run the app spends about a
    minute building its environment before it answers at all.  */
class ConvertifyEditor::Waiter  : public juce::Thread
{
public:
    Waiter() : juce::Thread ("Convertify: waiting for the engine") {}
    ~Waiter() override { stopThread (3000); }

    void run() override
    {
        if (convertify::engineIsAnswering()) { ready = true; return; }

        if (! convertify::askTheAppToStart())
        {
            missing = true;
            return;
        }

        //  Ninety seconds: long enough for a first run, which installs its own Python.
        ready = convertify::waitForTheEngine (90, [this] { return threadShouldExit(); });
        if (! ready && ! threadShouldExit())
            slow = true;
    }

    std::atomic<bool> ready { false }, missing { false }, slow { false };
};

ConvertifyEditor::ConvertifyEditor (ConvertifyProcessor& p)
    : juce::AudioProcessorEditor (&p)
{
    setResizable (true, true);
    setResizeLimits (520, 420, 1600, 1400);
    setSize (900, 760);

    words.setJustificationType (juce::Justification::centred);
    words.setFont (juce::FontOptions (15.0f));
    addAndMakeVisible (words);

    button.setVisible (false);
    button.onClick = []
    {
        juce::URL ("https://github.com/koderking25/convertify/releases/latest").launchInDefaultBrowser();
    };
    addAndMakeVisible (button);

    sayWhatIsHappening ("Waking Convertify up...");
    waiter = std::make_unique<Waiter>();
    waiter->startThread();
    startTimerHz (8);
}

ConvertifyEditor::~ConvertifyEditor()
{
    stopTimer();
    waiter.reset();
}

void ConvertifyEditor::paint (juce::Graphics& g)
{
    //  Convertify's own green, so the plugin does not look like a stranger while it waits.
    g.fillAll (juce::Colour (0xff0e1511));
    if (! shown)
    {
        g.setColour (juce::Colour (0xff5fd79b));
        g.setFont (juce::FontOptions (30.0f, juce::Font::bold));
        g.drawText ("Convertify.", getLocalBounds().withTrimmedBottom (120),
                    juce::Justification::centred, false);
    }
}

void ConvertifyEditor::resized()
{
    auto area = getLocalBounds();
    if (page != nullptr)
        page->setBounds (area);
    words.setBounds (area.withSizeKeepingCentre (area.getWidth() - 60, 60).translated (0, 50));
    button.setBounds (area.withSizeKeepingCentre (200, 34).translated (0, 110));
}

void ConvertifyEditor::sayWhatIsHappening (const juce::String& text, bool isAProblem)
{
    words.setText (text, juce::dontSendNotification);
    words.setColour (juce::Label::textColourId,
                     isAProblem ? juce::Colour (0xfff28b7d) : juce::Colour (0xff90a497));
}

void ConvertifyEditor::timerCallback()
{
    if (waiter == nullptr || shown)
        return;

    if (waiter->ready)
    {
        stopTimer();
        showThePage();
    }
    else if (waiter->missing)
    {
        stopTimer();
        sayWhatIsHappening ("Convertify is not installed on this Mac.\n"
                            "The plugin is the window; the app does the work.", true);
        button.setVisible (true);
    }
    else if (waiter->slow)
    {
        stopTimer();
        sayWhatIsHappening ("Convertify is taking a long time to start.\n"
                            "Open it yourself, then close and reopen this.", true);
    }
    else if (convertify::findTheApp().exists())
    {
        sayWhatIsHappening ("Starting Convertify... the first time takes about a minute.");
    }
}

void ConvertifyEditor::showThePage()
{
    page = std::make_unique<juce::WebBrowserComponent>();
    addAndMakeVisible (*page);
    page->goToURL (convertify::pageUrl());
    page->setBounds (getLocalBounds());
    words.setVisible (false);
    button.setVisible (false);
    shown = true;
    repaint();
}
