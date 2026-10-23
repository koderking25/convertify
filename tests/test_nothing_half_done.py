"""A file in your Downloads folder should be a file that works.

Convertify used to write the conversion straight into the folder you chose. If ffmpeg stopped
half way, or the disk filled, what was left behind looked exactly like a finished file. These
check the two rules that replaced that: build it somewhere else and only move it over once it
has been looked at, and refuse to call something done when it plainly is not.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "convertify"))
sys.path.insert(0, str(ROOT / "shared"))
for v in ("CLAVINOVA_STATE", "CONVERTIFY_STATE", "CONVERTIFY_WORK", "CONVERTIFY_SAVE"):
    os.environ[v] = tempfile.mkdtemp()

import engine  # noqa: E402

FFMPEG = next((p for p in ["/Applications/Convertify.app/Contents/Resources/tools/bin/ffmpeg",
                           "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"] if Path(p).exists()),
              None)
if FFMPEG:
    engine.FFMPEG = FFMPEG


def a_tone(seconds=4.0):
    out = Path(tempfile.mkdtemp()) / "tone.m4a"
    subprocess.run([engine.FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-c:a", "aac", str(out)], check=True)
    return out


@unittest.skipUnless(FFMPEG, "no ffmpeg to test with")
class RefusesWhatIsNotReal(unittest.TestCase):
    def test_an_empty_file_is_not_a_conversion(self):
        empty = Path(tempfile.mkdtemp()) / "x.mp3"
        empty.write_bytes(b"")
        with self.assertRaises(RuntimeError) as caught:
            engine.check_it_is_real(empty, "mp3")
        self.assertIn("empty", str(caught.exception))

    def test_a_file_that_was_never_written_is_not_a_conversion(self):
        with self.assertRaises(RuntimeError):
            engine.check_it_is_real(Path(tempfile.mkdtemp()) / "nope.mp3", "mp3")

    def test_something_that_is_not_midi_is_refused_as_midi(self):
        fake = Path(tempfile.mkdtemp()) / "x.mid"
        fake.write_bytes(b"this is not a midi file, it is a sentence" * 40)
        with self.assertRaises(RuntimeError) as caught:
            engine.check_it_is_real(fake, "midi")
        self.assertIn("MIDI", str(caught.exception))

    def test_a_real_midi_header_passes(self):
        real = Path(tempfile.mkdtemp()) / "x.mid"
        real.write_bytes(b"MThd" + b"\0" * 2000)
        engine.check_it_is_real(real, "midi")

    def test_audio_cut_far_short_of_what_was_asked_for_is_refused(self):
        short = a_tone(2.0)
        with self.assertRaises(RuntimeError) as caught:
            engine.check_it_is_real(short, "m4a", expected_seconds=300)
        self.assertIn("cut short", str(caught.exception))

    def test_audio_of_about_the_right_length_passes(self):
        engine.check_it_is_real(a_tone(10.0), "m4a", expected_seconds=10)

    def test_the_real_converter_produces_something_that_passes(self):
        out = Path(tempfile.mkdtemp()) / "out.mp3"
        engine.convert_to(a_tone(5.0), out, "mp3", "192", "T", "A")
        engine.check_it_is_real(out, "mp3", expected_seconds=5)


@unittest.skipUnless(FFMPEG, "no ffmpeg to test with")
class NothingAppearsUntilItIsDone(unittest.TestCase):
    def test_a_conversion_that_fails_leaves_the_folder_as_it_was(self):
        downloads = Path(tempfile.mkdtemp())
        work = Path(tempfile.mkdtemp())
        building = work / "built.mp3"
        broken = Path(tempfile.mkdtemp()) / "not-audio.m4a"
        broken.write_bytes(b"certainly not audio" * 50)
        with self.assertRaises(Exception):
            engine.convert_to(broken, building, "mp3", "192", "T", "A")
        self.assertEqual(list(downloads.iterdir()), [],
                         "a failed conversion put something in the destination folder")

    def test_the_finished_file_arrives_whole_and_named(self):
        downloads = Path(tempfile.mkdtemp())
        built = Path(tempfile.mkdtemp()) / "built.mp3"
        engine.convert_to(a_tone(3.0), built, "mp3", "192", "T", "A")
        size = built.stat().st_size
        landed = engine.put_in_place(built, downloads / "Song.mp3")
        self.assertEqual(landed.name, "Song.mp3")
        self.assertEqual(landed.stat().st_size, size)
        self.assertFalse(built.exists(), "the working copy should not be left behind")

    def test_it_never_writes_over_something_that_is_already_there(self):
        downloads = Path(tempfile.mkdtemp())
        (downloads / "Song.mp3").write_bytes(b"something precious")
        built = Path(tempfile.mkdtemp()) / "built.mp3"
        engine.convert_to(a_tone(3.0), built, "mp3", "192", "T", "A")
        landed = engine.put_in_place(built, downloads / "Song.mp3")
        self.assertEqual(landed.name, "Song 2.mp3")
        self.assertEqual((downloads / "Song.mp3").read_bytes(), b"something precious")

    def test_a_folder_it_cannot_write_to_is_refused_before_anything_happens(self):
        locked = Path(tempfile.mkdtemp())
        os.chmod(locked, 0o500)
        try:
            self.assertFalse(os.access(locked, os.W_OK))
        finally:
            os.chmod(locked, 0o700)


if __name__ == "__main__":
    unittest.main(verbosity=2)
