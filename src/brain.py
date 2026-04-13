"""Car-HUD Brain — Smart command processing.
Online: Gemini Flash for natural understanding + gTTS for voice.
Offline: Local intent matcher + espeak.
Caches responses to save tokens and enable offline answers.
"""

import os
import json
import time
import hashlib
import subprocess

GEMINI_KEY = ""
CONFIG_FILE = "/home/chrismslist/car-hud/.keys.json"
ONLINE_CACHE_FILE = "/tmp/car-hud-online"
CACHE_FILE = "/home/chrismslist/car-hud/.response_cache.json"

# Words that indicate time-sensitive queries (don't cache these)
TIMELY_WORDS = {"time", "weather", "date", "today", "tonight", "now",
                "current", "right now", "temperature", "forecast"}

# Load API key
try:
    with open(CONFIG_FILE) as f:
        GEMINI_KEY = json.load(f).get("gemini", "")
except Exception:
    pass


def _cache_key(text):
    """Normalize text to a cache key."""
    normalized = " ".join(text.lower().split())
    # Remove wake words
    for w in ["hey honda", "a honda", "honda"]:
        normalized = normalized.replace(w, "").strip()
    return hashlib.md5(normalized.encode()).hexdigest()


def _is_timely(text):
    """Check if query is time-sensitive (shouldn't be cached)."""
    words = set(text.lower().split())
    return bool(words & TIMELY_WORDS)


def _load_cache():
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        # Keep cache under 200 entries
        if len(cache) > 200:
            items = sorted(cache.items(), key=lambda x: -x[1].get("hits", 0))
            cache = dict(items[:150])
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


def _word_overlap(a, b):
    """Score similarity between two strings by word overlap."""
    wa = set(a.lower().split()) - {"hey", "honda", "a", "the", "to", "my", "is", "it", "can", "you", "what"}
    wb = set(b.lower().split()) - {"hey", "honda", "a", "the", "to", "my", "is", "it", "can", "you", "what"}
    if not wa or not wb:
        return 0
    overlap = len(wa & wb)
    total = min(len(wa), len(wb))
    return overlap / total if total > 0 else 0


def cache_lookup(text):
    """Fuzzy cache lookup — finds best match with high word overlap.
    Returns (action, target, reply, source) or None.
    """
    if _is_timely(text):
        return None

    cache = _load_cache()

    # Try exact match first
    key = _cache_key(text)
    entry = cache.get(key)
    if entry:
        entry["hits"] = entry.get("hits", 0) + 1
        _save_cache(cache)
        return entry["action"], entry["target"], entry["reply"], "cache"

    # Fuzzy match — need 80%+ word overlap
    best_score = 0
    best_entry = None
    for k, entry in cache.items():
        score = _word_overlap(text, entry.get("text", ""))
        if score > best_score:
            best_score = score
            best_entry = entry

    if best_score >= 0.8 and best_entry:
        best_entry["hits"] = best_entry.get("hits", 0) + 1
        _save_cache(cache)
        return best_entry["action"], best_entry["target"], best_entry["reply"], "cache"

    return None


def cache_store(text, action, target, reply):
    """Store a response in cache."""
    if _is_timely(text) or action == "unknown":
        return
    key = _cache_key(text)
    cache = _load_cache()
    cache[key] = {"action": action, "target": target, "reply": reply,
                  "text": text, "hits": 1, "time": time.time()}
    _save_cache(cache)


def is_online():
    """Quick connectivity check (cached for 30s)."""
    try:
        with open(ONLINE_CACHE_FILE) as f:
            data = json.load(f)
            if time.time() - data.get("time", 0) < 30:
                return data.get("online", False)
    except Exception:
        pass

    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                           capture_output=True, timeout=4)
        online = r.returncode == 0
    except Exception:
        online = False

    try:
        with open(ONLINE_CACHE_FILE, "w") as f:
            json.dump({"online": online, "time": time.time()}, f)
    except Exception:
        pass
    return online


def gemini_understand(text):
    """Send text to Gemini Flash for smart intent parsing.
    Returns (action, target, response_text) or None on failure.
    """
    if not GEMINI_KEY:
        return None

    try:
        import urllib.request
        import urllib.error

        prompt = f"""You are Honda, a car HUD voice assistant in a 2014 Honda Accord Hybrid. Be concise and helpful.

Available actions:
- show: camera, music, map, system, home, vehicle, help
- theme: blue, red, green, amber, day, night, auto
- music: play, pause, next, previous, stop
- brightness: up, down
- wifi: scan, connect, disconnect
- pair/unpair: phone
- info: any general question (YOU answer it directly in reply)

User said: "{text}"

Rules:
- For commands: set action/target and give a SHORT confirmation in reply (3-5 words max)
- For questions: use action "info", target "general", and ANSWER the question in reply (1-2 sentences max)
- For weather: give a general answer since you don't have live data
- Be natural and friendly but very brief — this is spoken aloud while driving
- The speech recognition may garble words — infer what they likely meant

Respond with ONLY this JSON, nothing else:
{{"action": "...", "target": "...", "reply": "..."}}"""

        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100}
        }).encode()

        # Try models in order: newest first, fall back on error
        models = [
            ("gemini-3-flash-preview", "3.0F"),
            ("gemini-2.5-flash", "2.5F"),
            ("gemini-2.0-flash", "2.0F"),
        ]

        for model_id, model_tag in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_KEY}"
                req = urllib.request.Request(url, data=body,
                                             headers={"Content-Type": "application/json"})
                resp = urllib.request.urlopen(req, timeout=5)
                result = json.loads(resp.read())

                reply_text = result["candidates"][0]["content"]["parts"][0]["text"]
                reply_text = reply_text.strip()
                if reply_text.startswith("```"):
                    reply_text = reply_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                parsed = json.loads(reply_text)
                return (parsed.get("action"), parsed.get("target"),
                        parsed.get("reply", ""), model_tag)
            except Exception:
                continue  # try next model

        return None

    except Exception:
        return None


def smart_tts(text):
    """Speak text — gTTS online, espeak offline. Returns immediately (non-blocking)."""
    def _find_output():
        # Find a playback device that isn't busy
        for card in range(5):
            path = f"/proc/asound/card{card}/id"
            if os.path.exists(path):
                with open(path) as f:
                    name = f.read().strip()
                if name == "C925e":
                    continue
                if name in ("Headphones", "vc4hdmi", "Audio", "Card"):
                    return card
        return None

    dev = "default"

    if is_online():
        try:
            # gTTS — natural sounding, saves to temp file
            import urllib.request
            import urllib.parse
            tts_text = urllib.parse.quote(text[:200])
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en&q={tts_text}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=4)
            audio_data = resp.read()

            tmp = "/tmp/car-hud-tts.mp3"
            with open(tmp, "wb") as f:
                f.write(audio_data)

            # Convert mp3 to stereo wav and play on USB audio
            play_dev = dev
            for c in range(6):
                p = f"/proc/asound/card{c}/id"
                if os.path.exists(p):
                    with open(p) as f:
                        if f.read().strip() in ("Audio", "Card"):
                            play_dev = f"plughw:{c},0"
                            break
            subprocess.Popen(
                f"ffmpeg -i {tmp} -ar 48000 -ac 2 -f wav - 2>/dev/null | aplay -D {play_dev} -q 2>/dev/null",
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass

    # Offline fallback — espeak → convert to stereo 48kHz → play
    try:
        # Find USB audio card for playback
        play_dev = dev
        for c in range(6):
            p = f"/proc/asound/card{c}/id"
            if os.path.exists(p):
                with open(p) as f:
                    if f.read().strip() in ("Audio", "Card"):
                        play_dev = f"plughw:{c},0"
                        break

        # espeak → ffmpeg (mono→stereo 48k) → aplay
        subprocess.Popen(
            f'espeak -v en-us+f3 -s 145 -p 60 -a 180 --stdout "{text}" | '
            f'ffmpeg -i - -ar 48000 -ac 2 -f wav - 2>/dev/null | '
            f'aplay -D {play_dev} -q 2>/dev/null',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def process_command(text):
    """Smart command processing with learning + caching.
    Returns (action, target, spoken_response, source).
    """
    from wordlearn import correct, learn

    # 0. Apply learned word corrections
    corrected_text, correction_confidence, phrase_match = correct(text)
    if corrected_text != text:
        # Log the correction for debugging
        try:
            with open("/tmp/car-hud-voice.log", "a") as f:
                f.write(f"[AutoCorrect] '{text}' -> '{corrected_text}'\n")
        except Exception:
            pass

    # Check if phrase learning already knows this exact pattern
    if phrase_match and correction_confidence > 0:
        parts = phrase_match.split(":", 1)
        if len(parts) == 2:
            action, target = parts
            RESPONSES = {
                ("show", "camera"):  "Showing camera",
                ("show", "music"):   "Now playing",
                ("show", "home"):    "Going home",
                ("theme", "blue"):   "Blue theme",
                ("theme", "red"):    "Red theme",
                ("theme", "green"):  "Green theme",
                ("theme", "amber"):  "Amber theme",
                ("theme", "day"):    "Day mode",
                ("theme", "night"):  "Night mode",
                ("music", "play"):   "Playing",
                ("music", "pause"):  "Paused",
                ("music", "next"):   "Next track",
                ("music", "previous"): "Previous track",
            }
            reply = RESPONSES.get((action, target), f"{action} {target}")
            return action, target, reply, "learned"

    # Use corrected text for all further processing
    use_text = corrected_text if correction_confidence > 0 else text

    # 1. Check cache first (fastest)
    cached = cache_lookup(use_text)
    if cached:
        action, target, reply, source = cached
        return action, target, reply, "cache"

    # 2. Try Gemini if online
    if is_online() and GEMINI_KEY:
        result = gemini_understand(use_text)
        if result:
            action, target, reply, model_tag = result
            if action and action != "unknown":
                cache_store(use_text, action, target, reply)
                # Learn from this success — map original garbled text to result
                learn(text, action, target)
                return action, target, reply, f"ai:{model_tag}"

    # 3. Local fallback
    from intent import match_intent
    result = match_intent(text)
    if result:
        action, target, confidence = result
        RESPONSES = {
            ("show", "camera"):  "Showing camera",
            ("show", "music"):   "Now playing",
            ("show", "map"):     "Opening navigation",
            ("show", "system"):  "System status",
            ("show", "home"):    "Going home",
            ("show", "vehicle"): "Vehicle info",
            ("show", "help"):    "Here are the commands",
            ("music", "play"):   "Playing",
            ("music", "pause"):  "Paused",
            ("music", "next"):   "Next track",
            ("music", "previous"): "Previous track",
            ("theme", "blue"):   "Blue theme",
            ("theme", "red"):    "Red theme",
            ("theme", "green"):  "Green theme",
            ("theme", "amber"):  "Amber theme",
            ("theme", "day"):    "Day mode",
            ("theme", "night"):  "Night mode",
            ("theme", "auto"):   "Auto mode",
            ("brightness", "up"):   "Brighter",
            ("brightness", "down"): "Dimmer",
            ("pair", "phone"):   "Pairing phone",
            ("unpair", "phone"): "Phone removed",
            ("wifi", "scan"):    "Scanning networks",
        }
        reply = RESPONSES.get((action, target), f"{action} {target}")
        return action, target, reply, "local"

    return "unknown", text, "I didn't understand that", "local"
