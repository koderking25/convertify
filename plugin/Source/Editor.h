#pragma once
#include <juce_gui_extra/juce_gui_extra.h>
#include <juce_audio_processors/juce_audio_processors.h>

class ConvertifyProcessor;

/*  The plugin window is Convertify's own page, shown in a web view.

    Not a copy of it, not a smaller version of it: the same page, served by the same engine,
    so there is one interface to keep working and it cannot drift out of step with the app.  */
class ConvertifyEditor  : public juce::AudioProcessorEditor,
                          private juce::Timer
{
public:
    explicit ConvertifyEditor (ConvertifyProcessor&);
    ~ConvertifyEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override;
    void showThePage();
    void sayWhatIsHappening (const juce::String& words, bool isAProblem = false);

    class Waiter;
    std::unique_ptr<Waiter> waiter;
    std::unique_ptr<juce::WebBrowserComponent> page;
    juce::Label words;
    juce::TextButton button { "Get Convertify" };
    bool shown = false;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ConvertifyEditor)
};
