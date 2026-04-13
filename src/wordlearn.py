"""Word learning system for voice recognition.
Learns from Vosk transcription mistakes by tracking what Gemini
actually understood. Over time, auto-corrects common mishearings
before sending to the brain.

Example: Vosk hears "color chicken" but Gemini understood "color green"
         → learns that "chicken" often means "green" in this context
         → next time Vosk says "chicken", auto-corrects to "green"
"""

import json
import os
import time

LEARN_FILE = "/home/chrismslist/car-hud/.word_corrections.json"
MAX_ENTRIES = 1000


def _load():
    try:
        with open(LEARN_FILE) as f:
            return json.load(f)
    except Exception:
        return {"words": {}, "phrases": {}, "wake": {}}


def _save(data):
    try:
        # Trim if too large — keep most-used entries
        for category in ["words", "phrases", "wake"]:
            if len(data.get(category, {})) > MAX_ENTRIES:
                sorted_items = sorted(data[category].items(),
                                  key=lambda x: -x[1].get("hits", 0))
                data[category] = dict(sorted_items[:MAX_ENTRIES])
        with open(LEARN_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def learn(vosk_text, actual_action, actual_target):
    """Learn from a successful Gemini interpretation."""
    data = _load()
    vosk_words = vosk_text.lower().split()
    target_lower = actual_target.lower()

    # 1. Word-level: map garbled word to intended target
    if target_lower and target_lower not in vosk_words:
        # Find the word that's likely the garbled target (usually near end)
        for word in reversed(vosk_words):
            if word in ("the", "a", "to", "my", "is", "it", "hey", "honda", "can", "you", "show", "make", "set"):
                continue
            if word not in data["words"]:
                data["words"][word] = {"corrections": {}, "hits": 0}
            data["words"][word]["corrections"][target_lower] = data["words"][word]["corrections"].get(target_lower, 0) + 1
            data["words"][word]["hits"] += 1
            break

    # 2. Phrase-level: map whole cleaned phrase to intent
    clean = [w for w in vosk_words if w not in {"hey", "honda", "hondo", "a", "the", "please", "can", "you", "to"}]
    if clean:
        phrase_key = " ".join(clean[:4])
        if phrase_key not in data["phrases"]:
            data["phrases"][phrase_key] = {"intent": f"{actual_action}:{actual_target}", "hits": 0}
        data["phrases"][phrase_key]["hits"] += 1

    _save(data)


def learn_wake(garbled_wake):
    """Learn words that Vosk consistently hears when we said 'Hey Honda'."""
    data = _load()
    if "wake" not in data: data["wake"] = {}
    
    words = garbled_wake.lower().split()
    for w in words:
        if w in ("honda", "hondo"): continue
        if w not in data["wake"]:
            data["wake"][w] = {"hits": 0}
        data["wake"][w]["hits"] += 1
    _save(data)


def correct(text):
    """Apply learned corrections. Returns (corrected_text, confidence, phrase_intent)."""
    data = _load()
    words = text.lower().split()
    corrected = list(words)
    corrections_made = 0

    # Apply word mappings
    for i, word in enumerate(words):
        if word in data["words"]:
            entry = data["words"][word]
            if entry["corrections"]:
                best_corr, count = max(entry["corrections"].items(), key=lambda x: x[1])
                if count >= 2:
                    corrected[i] = best_corr
                    corrections_made += 1

    # Check phrase mappings
    clean = [w for w in words if w not in {"hey", "honda", "hondo", "a", "the", "please", "can", "you", "to"}]
    phrase_key = " ".join(clean[:4])
    phrase_intent = None
    if phrase_key in data["phrases"]:
        if data["phrases"][phrase_key]["hits"] >= 2:
            phrase_intent = data["phrases"][phrase_key]["intent"]

    # Check learned wake words
    is_learned_wake = False
    for w in words:
        if w in data.get("wake", {}) and data["wake"][w]["hits"] >= 3:
            is_learned_wake = True
            break

    confidence = min(1.0, corrections_made * 0.4 + (0.5 if phrase_intent else 0))
    return " ".join(corrected), confidence, phrase_intent, is_learned_wake


def get_stats():
    """Return learning stats."""
    data = _load()
    return {
        "words_learned": len(data["words"]),
        "phrases_learned": len(data["phrases"]),
        "total_hits": sum(e["hits"] for e in data["words"].values())
    }


# ── Audio parameter reinforcement learning ──
AUDIO_PARAMS_FILE = "/home/chrismslist/car-hud/.audio_params.json"

def load_audio_params():
    """Load learned audio parameters."""
    defaults = {
        "mic1_base_gain": 5.0,
        "mic2_base_gain": 1.5,
        "target_speech_rms": 5000.0,
        "voice_threshold_mult": 2.5,  # noise_floor * this = voice detected
        "success_count": 0,
        "fail_count": 0,
    }
    try:
        with open(AUDIO_PARAMS_FILE) as f:
            saved = json.load(f)
            defaults.update(saved)
    except Exception:
        pass
    return defaults


def reinforce_audio(success, mic1_gain, mic2_gain, mic1_snr, mic2_snr):
    """Update audio parameters based on whether recognition succeeded.
    Called after every command attempt.
    success=True: Gemini/local understood the command
    success=False: got 'unknown' or garbled
    """
    params = load_audio_params()

    if success:
        params["success_count"] = params.get("success_count", 0) + 1
        # Successful — reinforce current gain levels
        params["mic1_base_gain"] = params["mic1_base_gain"] * 0.9 + mic1_gain * 0.1
        params["mic2_base_gain"] = params["mic2_base_gain"] * 0.9 + mic2_gain * 0.1
    else:
        params["fail_count"] = params.get("fail_count", 0) + 1
        # Failed — try adjusting: if gain is low, bump it up
        if mic1_snr < 3:
            params["mic1_base_gain"] = min(25, params["mic1_base_gain"] * 1.15)
        if mic2_snr < 3:
            params["mic2_base_gain"] = min(25, params["mic2_base_gain"] * 1.15)
        # Also lower the voice detection threshold to be more sensitive
        params["voice_threshold_mult"] = max(1.5, params["voice_threshold_mult"] * 0.95)

    try:
        with open(AUDIO_PARAMS_FILE, "w") as f:
            json.dump(params, f)
    except Exception:
        pass

    return params


# ── Voice profile learning ──
VOICE_PROFILE_FILE = "/home/chrismslist/car-hud/.voice_profile.json"

def update_voice_profile(rms_during_speech, frequency_estimate=None):
    """Learn the user's voice characteristics over time.
    Tracks average speaking volume and dominant frequency range.
    """
    profile = {"avg_rms": 3000, "samples": 0, "min_rms": 1000, "max_rms": 8000}
    try:
        with open(VOICE_PROFILE_FILE) as f:
            profile = json.load(f)
    except Exception:
        pass

    profile["samples"] = profile.get("samples", 0) + 1
    n = min(profile["samples"], 100)  # weighted average over last 100 samples
    profile["avg_rms"] = profile["avg_rms"] * ((n-1)/n) + rms_during_speech * (1/n)
    profile["min_rms"] = min(profile.get("min_rms", rms_during_speech), rms_during_speech)
    profile["max_rms"] = max(profile.get("max_rms", rms_during_speech), rms_during_speech)

    try:
        with open(VOICE_PROFILE_FILE, "w") as f:
            json.dump(profile, f)
    except Exception:
        pass

    return profile
