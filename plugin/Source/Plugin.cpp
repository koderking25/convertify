#include "Plugin.h"
#include "Editor.h"

ConvertifyProcessor::ConvertifyProcessor()
    : AudioProcessor (BusesProperties()
                          .withInput  ("In",  juce::AudioChannelSet::stereo(), true)
                          .withOutput ("Out", juce::AudioChannelSet::stereo(), true))
{
}

bool ConvertifyProcessor::isBusesLayoutSupported (const BusesLayout& layouts) const
{
    //  Whatever shape the track is, as long as what goes out matches what came in. Nothing is
    //  being processed, so there is no reason to be fussy.
    return layouts.getMainInputChannelSet() == layouts.getMainOutputChannelSet()
        && ! layouts.getMainInputChannelSet().isDisabled();
}

void ConvertifyProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    //  Audio is left exactly as it arrived. Any output channel the host added beyond the
    //  input is silenced, rather than left holding whatever was in it.
    for (auto i = getTotalNumInputChannels(); i < getTotalNumOutputChannels(); ++i)
        buffer.clear (i, 0, buffer.getNumSamples());
}

void ConvertifyProcessor::processBlock (juce::AudioBuffer<double>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    for (auto i = getTotalNumInputChannels(); i < getTotalNumOutputChannels(); ++i)
        buffer.clear (i, 0, buffer.getNumSamples());
}

juce::AudioProcessorEditor* ConvertifyProcessor::createEditor()
{
    return new ConvertifyEditor (*this);
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new ConvertifyProcessor();
}
