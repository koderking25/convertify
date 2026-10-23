"""Song search (YouTube recordings, BitMidi MIDI files) and audio download.

Every request to an outside service goes through a pacer: a minimum gap per
service, and a long cooldown (remembered across restarts) if a service says
slow down. Search results are cached so repeat searches cost nothing.
"""
import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yt_dlp

import os

STATE = Path(os.environ.get("CLAVINOVA_STATE", Path(__file__).resolve().parent.parent / "state"))
STATE.mkdir(parents=True, exist_ok=True)
COOLDOWN_FILE = STATE / "cooldowns.json"
UA = "Midify/1.0 (personal, one request per search)"

MIN_GAP = {"youtube": 2.0, "bitmidi": 3.0}
COOLDOWN_S = {"youtube": 30 * 60, "bitmidi": 60 * 60}
MAX_SONG_SECONDS = 15 * 60
# How long a recording may be when only part of it is being made. The whole file is downloaded
# and then cut, so the question is how big that file is: about 58 MB an hour for YouTube audio,
# which at the 10 MB/s measured on a real download is six seconds an hour. Four hours is about
# 230 MB and half a minute, which is reasonable for taking five minutes out of a long concert or
# a live set. Beyond that it is a sleep video or a stream, and fetching half a gigabyte to use
# five minutes of it is not.
LONGEST_TO_FETCH = 4 * 60 * 60
BIGGEST_FILE = 300 * 1024 * 1024          # normally
BIGGEST_FILE_WHEN_TRIMMING = 600 * 1024 * 1024


class SlowDown(Exception):
    pass


class Pacer:
    def __init__(self):
        self.lock = threading.Lock()
        self.last = {}
        try:
            self.cool = json.loads(COOLDOWN_FILE.read_text())
        except Exception:  # noqa: BLE001
            self.cool = {}

    def wait(self, service):
        with self.lock:
            until = self.cool.get(service, 0)
            if time.time() < until:
                mins = int((until - time.time()) / 60) + 1
                raise SlowDown(f"{service} asked us to slow down. Searching it again in about {mins} min.")
            gap = MIN_GAP.get(service, 2.0) - (time.time() - self.last.get(service, 0))
            if gap > 0:
                time.sleep(gap)
            self.last[service] = time.time()

    def back_off(self, service):
        with self.lock:
            self.cool[service] = time.time() + COOLDOWN_S.get(service, 1800)
            try:
                COOLDOWN_FILE.write_text(json.dumps(self.cool))
            except OSError:
                pass


PACER = Pacer()
_cache = {}
_cache_lock = threading.Lock()


def _cached(key, fn, ttl=3600):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (time.time(), val)
    return val


def _is_rate_limit(msg):
    m = msg.lower()
    return "429" in m or "too many requests" in m or "rate-limit" in m or "rate limit" in m


# Every shape a YouTube link comes in, including the ones with a timestamp or a playlist stuck on
# the end. Anything that is already a bare id is accepted as it is.
# Exactly eleven characters and no more: "hYH80WGPet8x" is not a video id with a spare letter, it
# is not a video id. Without the guard at the end, the first eleven characters of anything matched.
_ID = r"(?P<id>[A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])"
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
LINK_SHAPES = [
    re.compile(r"[?&]v=" + _ID),                                  # youtube.com/watch?v=ID
    re.compile(r"youtu\.be/" + _ID),                              # youtu.be/ID
    re.compile(r"/(?:shorts|live|embed|v)/" + _ID),               # shorts, live, embeds
    re.compile(r"^" + _ID + r"$"),                                # someone pasted just the id
]


def youtube_id(text):
    """The video id inside whatever was pasted, or None if there is not one.

    Deliberately strict about length: an eleven character id is the only thing YouTube uses, so
    anything else is a playlist, a channel, or a mistake."""
    text = (text or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if "://" in lowered or lowered.startswith("www."):
        host = lowered.split("://", 1)[-1].split("/", 1)[0].split("@")[-1].split(":")[0]
        if not any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS):
            return None                                   # some other site that happens to use ?v=
    for shape in LINK_SHAPES:
        found = shape.search(text)
        if found:
            return found.group("id")
    return None


def looks_like_link(text):
    """Did they paste a link rather than type a song name?"""
    text = (text or "").strip().lower()
    return text.startswith(("http://", "https://", "www.", "youtu.be/", "youtube.com", "m.youtube.com",
                            "music.youtube.com"))


def video_info(link_or_id):
    """Title and length for one video, so a pasted link can be shown before it is made."""
    video_id = youtube_id(link_or_id)
    if not video_id:
        raise ValueError("That does not look like a YouTube link. Copy the address from the "
                         "browser's address bar, or from Share then Copy link.")

    def run():
        PACER.wait("youtube")
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20}
        import yt_dlp
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        seconds = info.get("duration")
        return {"id": video_id, "title": (info.get("title") or "Song")[:150],
                "duration": seconds, "channel": info.get("uploader") or "",
                "thumb": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                "too_long": bool(seconds and seconds > MAX_SONG_SECONDS)}

    return _cached(("ytinfo", video_id), run)


def search_youtube(query, n=8):
    def run():
        PACER.wait("youtube")
        opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                "extract_flat": "in_playlist", "socket_timeout": 20}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
        except Exception as e:  # noqa: BLE001
            if _is_rate_limit(str(e)):
                PACER.back_off("youtube")
                raise SlowDown("YouTube asked us to slow down. Try again in about 30 minutes.")
            raise
        out = []
        for e in (info or {}).get("entries") or []:
            vid = e.get("id")
            if not vid or e.get("live_status") in ("is_live", "is_upcoming"):
                continue
            dur = e.get("duration")
            out.append({
                "id": vid,
                "title": e.get("title") or "Untitled",
                "channel": e.get("channel") or e.get("uploader") or "",
                "duration": int(dur) if dur else None,
                "thumb": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                "too_long": bool(dur and dur > MAX_SONG_SECONDS),
            })
        for hit in out:
            remember_video(hit)
        return out
    return _cached(("yt", query.lower().strip()), run)


def remember_video(d):
    """Treat a search result as the answer to "what is this video?".

    A search already knows the title, the channel and the length of everything it found, which is
    everything video_info returns. Without this, picking a result and converting it paid for a
    second lookup of the same video: measured at 2.1 seconds of pure waiting before the download
    could even start. Only remember it when the length is known, because the length is what
    decides whether a recording is too long to take on."""
    vid, dur = d.get("id"), d.get("duration")
    if not vid or not dur:
        return
    with _cache_lock:
        _cache[("ytinfo", vid)] = (time.time(), {
            "id": vid,
            "title": (d.get("title") or "Song")[:150],
            "duration": int(dur),
            "channel": d.get("channel") or "",
            "thumb": d.get("thumb") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
            "too_long": bool(dur > MAX_SONG_SECONDS),
        })


_FILLER = {"the", "and", "feat", "piano", "cover", "version", "official", "lyrics", "audio", "video",
           "tutorial", "easy", "midi", "song", "music", "remastered", "live", "instrumental"}


def _words(s):
    return re.findall(r"[a-z0-9']+", (s or "").lower().replace("_", " "))


def relevant(query, name):
    """BitMidi's search is loose ("someone you loved" returns "Someone You Need").
    Keep a result only if it has the words that were typed, ignoring filler."""
    want = [w for w in _words(query) if len(w) >= 3 and w not in _FILLER]
    if not want:
        return True
    have = set(_words(name))
    need = len(want) if len(want) <= 3 else math.ceil(len(want) * 2 / 3)
    return sum(w in have for w in want) >= need


def search_bitmidi(query, n=5):
    """BitMidi search API. Downloads are left to the user in their browser:
    bitmidi.com/robots.txt asks automated tools to stay out of /uploads/."""
    def run():
        PACER.wait("bitmidi")
        url = "https://bitmidi.com/api/midi/search?" + urllib.parse.urlencode({"q": query, "page": 0, "pageSize": 15})
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                PACER.back_off("bitmidi")
                raise SlowDown("BitMidi asked us to slow down. Try again in an hour.")
            raise
        res = (data.get("result") or {}).get("results") or []
        out = [{"name": x.get("name", "").removesuffix(".mid"),
                "page": "https://bitmidi.com" + x["url"],
                "plays": x.get("plays") or 0} for x in res if x.get("url", "").startswith("/")]
        return [x for x in out if relevant(query, x["name"])][:n]
    return _cached(("bm", query.lower().strip()), run)


def friendly_download_error(msg):
    m = msg.lower()
    if _is_rate_limit(m):
        PACER.back_off("youtube")
        return "YouTube asked us to slow down. Wait about 30 minutes, or drop in an audio file instead."
    if "sign in to confirm your age" in m or "age-restricted" in m or "inappropriate for some users" in m:
        return "That video is age-restricted, so it cannot be downloaded. Pick a different result."
    if "private video" in m:
        return "That video is private. Pick a different result."
    if "not available in your country" in m or "geo" in m and "block" in m:
        return "That video is blocked in your country. Pick a different result."
    if "video unavailable" in m or "has been removed" in m:
        return "That video is unavailable. Pick a different result."
    if "sign in to confirm you" in m and "bot" in m:
        PACER.back_off("youtube")
        return "YouTube thinks this is a bot right now. Wait a while, or drop in an audio file instead."
    if "challenge" in m or "javascript" in m or "js runtime" in m or "nsig" in m or "signature" in m:
        return ("YouTube changed something and the downloader needs an update. "
                "Click 'Update downloader' at the bottom of the page, then try again.")
    if "403" in m or "forbidden" in m:
        return ("YouTube refused the download three times. This is usually temporary: wait a minute "
                "and try again. If it keeps happening, click 'Update downloader' at the bottom of "
                "the page.")
    if "too long or not downloadable" in m or "does not pass filter" in m:
        longest = int(MAX_SONG_SECONDS // 60)
        hours = int(LONGEST_TO_FETCH // 3600)
        return (f"That recording is longer than {longest} minutes, so Midify will not make all of "
                "it. Tick 'Only make the first few minutes' above the search box, then try again. "
                f"That works for recordings up to {hours} hours long.")
    if "max_filesize" in m or "larger than max" in m:
        return "That file is too big. Pick a shorter video."
    if "timed out" in m or "urlopen error" in m or "network" in m or "connection" in m:
        return "Could not reach YouTube. Check your internet connection and try again."
    return "The download failed. Try a different result, or drop in an audio file instead."


DOWNLOAD_ATTEMPTS = 3

# Things that will not improve by asking again: no point making someone wait through three tries.
PERMANENT_FAILURES = ("private video", "age-restricted", "sign in to confirm your age",
                      "video unavailable", "has been removed", "not available in your country",
                      "max_filesize", "larger than max", "members-only", "is live",
                      "this live event", "inappropriate for some users")


def _is_permanent(message):
    low = message.lower()
    return any(bad in low for bad in PERMANENT_FAILURES)


class Stalled(Exception):
    """Bytes stopped arriving long enough that waiting further is not worth it."""


# How long a download may go without a single byte before it is treated as stuck. Generous,
# because a slow connection still delivers something now and then; a dead one delivers nothing.
STALL_AFTER = 45
SOCKET_PATIENCE = 60


def _now():
    """The clock, named so a test can move it without touching time.time for everything else.

    Patching time.time globally also changes what the rate limiter sees, and it waits in a loop
    until the clock says it may go: with a frozen clock that loop never ends."""
    return time.time()

# A 403 means the address we were given has been refused and a new one is needed, so whatever
# arrived under it is worthless. Anything else, including a stall or a timeout, is worth
# carrying on from.
_FRESH_ADDRESS_WANTED = ("403", "forbidden", "unable to download api page", "expired")


def _needs_a_fresh_address(message):
    low = message.lower()
    return any(bit in low for bit in _FRESH_ADDRESS_WANTED)


def duration_filter(seconds=None):
    """What lengths the downloader will accept.

    Normally fifteen minutes. When only part of a recording is being made, up to two hours, because
    the file is fetched whole and cut afterwards."""
    longest = LONGEST_TO_FETCH if seconds else MAX_SONG_SECONDS
    # Less than or equal, so a recording of exactly four hours is allowed. With "<" it was
    # refused while the message promised recordings "up to 4 hours".
    return f"duration <= {longest} & !is_live"


def download_youtube_audio(video_id, dest_dir, on_progress=None, cancel=None, seconds=None):
    """Download one video's audio into dest_dir. Returns the file path.

    `seconds` is how much of it is wanted. When it is given, two things change: a recording longer
    than Midify's usual limit is allowed, because only part of it is being made, and only that part
    is fetched. Five minutes of a twenty six minute concert is a fifth of the download."""
    dest_dir = Path(dest_dir)

    moved = {"bytes": 0, "at": _now(), "speed": 0.0, "eta": None, "total": 0}

    def hook(d):
        if cancel and cancel():
            raise yt_dlp.utils.DownloadCancelled("cancelled")
        if d.get("status") != "downloading":
            return
        got = d.get("downloaded_bytes") or 0
        now = _now()
        if got > moved["bytes"]:
            moved["bytes"], moved["at"] = got, now
        elif now - moved["at"] > STALL_AFTER:
            # Nothing has arrived for a long time. yt-dlp would sit on this until its socket
            # timeout, several times over, which on a poor connection is minutes of a window
            # that looks frozen. Give up on this attempt so the retry can start a fresh one.
            raise Stalled(f"nothing received for {int(now - moved['at'])}s")
        moved["speed"] = d.get("speed") or moved["speed"]
        moved["eta"] = d.get("eta")
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        moved["total"] = total or moved["total"]
        if on_progress and total:
            try:
                on_progress(min(1.0, got / total), dict(moved))
            except TypeError:
                on_progress(min(1.0, got / total))          # callers that only want the fraction

    def options(at_once, patience):
        return {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(dest_dir / "source.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "max_filesize": BIGGEST_FILE_WHEN_TRIMMING if seconds else BIGGEST_FILE,
            "retries": 5,
            "fragment_retries": 10,
            # A slow connection is not a broken one. Thirty seconds was short enough to give up
            # on a link that was still working, just not quickly.
            "socket_timeout": patience,
            # Some streams arrive in fragments, one request each. Fetched one at a time, the gaps
            # between requests are most of the wall clock; several at once fills them in. On a
            # thin connection that backfires, so a later attempt asks for one at a time.
            "concurrent_fragment_downloads": at_once,
            "continuedl": True,          # carry on from what arrived, rather than starting over
            "noprogress": True,          # it was printing a progress bar into the app's log
            "match_filter": yt_dlp.utils.match_filter_func(duration_filter(seconds)),
        }
    # Deliberately not asking for only the wanted part. Downloading a range makes yt-dlp stream the
    # audio through ffmpeg, and YouTube throttles that savagely: measured on a 26 minute concert,
    # five minutes took 155 seconds at 31 KB/s, while the whole 25 MB file took 3 seconds at
    # 10 MB/s. The file is small either way, so fetch it quickly and cut it when it is read.
    url = f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}"
    # YouTube hands out media addresses that sometimes refuse the very next request with a 403.
    # yt-dlp's own retries re-request the same address, which stays refused, so the whole download
    # fails on something that works a second later. Start again from scratch instead: a new
    # YoutubeDL asks YouTube for a fresh address. Seen on 9 October 2026, when the same video
    # failed and then downloaded immediately afterwards with nothing else changed.
    for attempt in range(DOWNLOAD_ATTEMPTS):
        if cancel and cancel():
            raise yt_dlp.utils.DownloadCancelled("cancelled")
        PACER.wait("youtube")
        # Four fragments at once is right on a good connection and wrong on a poor one, so a
        # second go asks for one at a time and waits longer for each.
        at_once = 4 if attempt == 0 else 1
        patience = SOCKET_PATIENCE + attempt * 30
        try:
            with yt_dlp.YoutubeDL(options(at_once, patience)) as ydl:
                ydl.download([url])
            break
        except yt_dlp.utils.DownloadCancelled:
            raise
        except Exception as e:                               # noqa: BLE001
            if attempt == DOWNLOAD_ATTEMPTS - 1 or _is_permanent(str(e)):
                raise
            # What is already here is worth keeping when the connection merely faltered: on a
            # slow link, throwing away most of a download and starting again is the difference
            # between finishing and never finishing. A refusal is different. YouTube hands out
            # media addresses that sometimes refuse the next request with a 403, and the part
            # file belongs to that dead address, so it has to go and be fetched afresh.
            if _needs_a_fresh_address(str(e)):
                for leftover in dest_dir.glob("source.*"):
                    leftover.unlink(missing_ok=True)
            time.sleep(2 + attempt * 3)
    files = [p for p in dest_dir.glob("source.*") if not p.name.endswith((".part", ".ytdl"))]
    if not files:
        raise RuntimeError("video too long or not downloadable")   # see friendly_download_error
    return max(files, key=lambda p: p.stat().st_size)
