#pragma once
#include <juce_audio_processors/juce_audio_processors.h>

/*  Convertify, as a plugin.

    Audio passes through untouched. This is not an effect pretending to be useful on the way
    past: it is a window, in a plugin slot, so that getting a track out of a video does not
    mean leaving what you are working in.  */
class ConvertifyProcessor  : public juce::AudioProcessor
{
public:
    ConvertifyProcessor();
    ~ConvertifyProcessor() override = default;

    void prepareToPlay (double, int) override {}
    void releaseResources() override {}
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    void processBlock (juce::AudioBuffer<double>&, juce::MidiBuffer&) override;
    bool supportsDoublePrecisionProcessing() const override   { return true; }
    bool isBusesLayoutSupported (const BusesLayout& layouts) const override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override                           { return true; }

    const juce::String getName() const override               { return "Convertify"; }
    bool acceptsMidi() const override                         { return false; }
    bool producesMidi() const override                        { return false; }
    bool isMidiEffect() const override                        { return false; }
    double getTailLengthSeconds() const override              { return 0.0; }

    int getNumPrograms() override                             { return 1; }
    int getCurrentProgram() override                          { return 0; }
    void setCurrentProgram (int) override                     {}
    const juce::String getProgramName (int) override          { return "Convertify"; }
    void changeProgramName (int, const juce::String&) override {}

    void getStateInformation (juce::MemoryBlock&) override    {}
    void setStateInformation (const void*, int) override      {}

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ConvertifyProcessor)
};
