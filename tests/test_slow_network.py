"""What happens when the connection is poor rather than absent.

A slow link and a broken one look the same from inside a download: bytes stop arriving. The
difference is whether waiting helps. These check the three decisions that follow from that:
give up on a stall rather than sit there, keep what has already arrived when it is still good,
and throw it away when the address it came from has been refused.
"""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))

import sources  # noqa: E402

# Nothing here touches YouTube, so the pacing between real requests is only making the tests
# wait. It is deliberately left alone everywhere else: it exists because hammering a service
# once got this machine banned from one.
sources.PACER.wait = lambda _who: None


class StallsAreNoticed(unittest.TestCase):
    def test_a_download_that_stops_dead_gives_up_rather_than_waiting(self):
        # Drive the hook the way yt-dlp would: bytes, then nothing, with time moved on.
        hook, clock = make_hook()
        hook({"status": "downloading", "downloaded_bytes": 1000, "total_bytes": 10_000})
        clock["now"] += sources.STALL_AFTER + 1
        with self.assertRaises(sources.Stalled):
            hook({"status": "downloading", "downloaded_bytes": 1000, "total_bytes": 10_000})

    def test_slow_but_moving_is_left_alone(self):
        hook, clock = make_hook()
        for i in range(1, 8):
            clock["now"] += sources.STALL_AFTER - 5      # very slow, but something each time
            hook({"status": "downloading", "downloaded_bytes": 1000 * i, "total_bytes": 10_000})
        # no exception is the whole point

    def test_progress_reports_what_is_happening(self):
        seen = []
        hook, clock = make_hook(on_progress=lambda f, how=None: seen.append((f, how)))
        hook({"status": "downloading", "downloaded_bytes": 2_500_000,
              "total_bytes": 5_000_000, "speed": 90_000, "eta": 40})
        frac, how = seen[-1]
        self.assertAlmostEqual(frac, 0.5, places=3)
        self.assertEqual(how["total"], 5_000_000)
        self.assertEqual(how["speed"], 90_000)
        self.assertEqual(how["eta"], 40)

    def test_a_caller_that_only_wants_the_fraction_still_works(self):
        seen = []
        hook, _ = make_hook(on_progress=lambda f: seen.append(f))   # Midify's own callback shape
        hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 4})
        self.assertEqual(seen, [0.25])


class KeepingWhatArrived(unittest.TestCase):
    def test_a_refusal_means_starting_again(self):
        for message in ["HTTP Error 403: Forbidden", "unable to download API page",
                        "This content has expired"]:
            self.assertTrue(sources._needs_a_fresh_address(message), message)

    def test_a_slow_or_flaky_line_does_not(self):
        for message in ["The read operation timed out", "nothing received for 48s",
                        "Connection reset by peer", "[Errno 54] Connection reset"]:
            self.assertFalse(sources._needs_a_fresh_address(message), message)

    def test_what_arrived_is_kept_across_a_timeout_and_thrown_away_after_a_refusal(self):
        for message, should_survive in [("The read operation timed out", True),
                                        ("HTTP Error 403: Forbidden", False)]:
            with self.subTest(message=message):
                folder = Path(__import__("tempfile").mkdtemp())
                half = folder / "source.m4a.part"
                half.write_bytes(b"x" * 4096)
                tries = {"n": 0}

                class PretendYDL:
                    def __init__(self, opts): self.opts = opts
                    def __enter__(self): return self
                    def __exit__(self, *a): return False

                    def download(self, _urls):
                        tries["n"] += 1
                        if tries["n"] == 1:
                            raise RuntimeError(message)
                        (folder / "source.m4a").write_bytes(b"y" * 9000)

                real_ydl, real_sleep = sources.yt_dlp.YoutubeDL, time.sleep
                sources.yt_dlp.YoutubeDL = PretendYDL
                time.sleep = lambda _s: None
                try:
                    got = sources.download_youtube_audio("x" * 11, folder)
                finally:
                    sources.yt_dlp.YoutubeDL, time.sleep = real_ydl, real_sleep
                self.assertEqual(got.name, "source.m4a")
                self.assertEqual(half.exists(), should_survive,
                                 "what had already arrived was handled wrongly")

    def test_a_poor_connection_gets_a_gentler_second_attempt(self):
        asked = []

        class PretendYDL:
            def __init__(self, opts): asked.append(opts)
            def __enter__(self): return self
            def __exit__(self, *a): return False

            def download(self, _urls):
                if len(asked) == 1:
                    raise RuntimeError("The read operation timed out")
                (folder / "source.m4a").write_bytes(b"y" * 9000)

        folder = Path(__import__("tempfile").mkdtemp())
        real_ydl, real_sleep = sources.yt_dlp.YoutubeDL, time.sleep
        sources.yt_dlp.YoutubeDL = PretendYDL
        time.sleep = lambda _s: None
        try:
            sources.download_youtube_audio("x" * 11, folder)
        finally:
            sources.yt_dlp.YoutubeDL, time.sleep = real_ydl, real_sleep
        self.assertEqual(asked[0]["concurrent_fragment_downloads"], 4)
        self.assertEqual(asked[1]["concurrent_fragment_downloads"], 1,
                         "the second attempt should stop asking for several at once")
        self.assertGreater(asked[1]["socket_timeout"], asked[0]["socket_timeout"])
        self.assertTrue(all(o["continuedl"] for o in asked), "it should carry on, not restart")


def make_hook(on_progress=None):
    """Build the downloader's own progress hook, with a clock we control.

    The clock is swapped through sources._now rather than time.time, because the rate limiter
    waits in a loop until the real clock passes a moment: freeze that and it never returns.
    """
    clock = {"now": 1000.0}
    grabbed = {}

    class Catcher:
        def __init__(self, opts): grabbed["hook"] = opts["progress_hooks"][0]
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def download(self, _u): raise RuntimeError("HTTP Error 403: Forbidden")

    folder = Path(__import__("tempfile").mkdtemp())
    real_ydl, real_now, real_sleep = sources.yt_dlp.YoutubeDL, sources._now, time.sleep
    sources.yt_dlp.YoutubeDL = Catcher
    sources._now = lambda: clock["now"]
    time.sleep = lambda _s: None          # the backoff between retries is not what is being read
    try:
        sources.download_youtube_audio("x" * 11, folder, on_progress=on_progress)
    except Exception:                                      # noqa: BLE001
        pass
    finally:
        sources.yt_dlp.YoutubeDL, time.sleep = real_ydl, real_sleep

    hook = grabbed["hook"]

    def run(d):
        was, sources._now = sources._now, lambda: clock["now"]
        try:
            return hook(d)
        finally:
            sources._now = was
    run.restore = lambda: setattr(sources, "_now", real_now)
    sources._now = real_now
    return run, clock


if __name__ == "__main__":
    unittest.main(verbosity=2)
