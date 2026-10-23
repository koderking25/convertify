# Convertify as a plugin: the same window, inside whatever you are working in.
#
# It is not an audio processor. Audio goes through it untouched. It exists so the thing you
# want is one plugin slot away instead of another application, and so the file it makes lands
# in the Finder in front of you.
cmake_minimum_required(VERSION 3.22)
project(ConvertifyPlugin VERSION 1.4.1)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_OSX_DEPLOYMENT_TARGET "11.0" CACHE STRING "")
# Both kinds of Mac, so this runs on Intel and Apple silicon alike.
set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "")

add_subdirectory(${JUCE_DIR} JUCE)

juce_add_plugin(ConvertifyPlugin
    PRODUCT_NAME            "Convertify"
    COMPANY_NAME            "Convertify"
    BUNDLE_ID               "tech.midify.convertify.plugin"
    PLUGIN_MANUFACTURER_CODE Cvfy
    PLUGIN_CODE             Cvt1
    FORMATS                 AU VST3 Standalone
    IS_SYNTH                FALSE
    NEEDS_MIDI_INPUT        FALSE
    NEEDS_MIDI_OUTPUT       FALSE
    IS_MIDI_EFFECT          FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS TRUE      # there is a search box in there
    COPY_PLUGIN_AFTER_BUILD TRUE
    AU_MAIN_TYPE            kAudioUnitType_Effect
    VST3_CATEGORIES         Fx Tools)

target_sources(ConvertifyPlugin PRIVATE
    Source/Plugin.cpp
    Source/Editor.cpp
    Source/Engine.cpp)

target_compile_definitions(ConvertifyPlugin PUBLIC
    JUCE_WEB_BROWSER=1          # the whole point: it shows Convertify's own page
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
    JUCE_DISPLAY_SPLASH_SCREEN=0)

target_link_libraries(ConvertifyPlugin PRIVATE
    juce::juce_audio_utils
    juce::juce_gui_extra
    PUBLIC
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags)
