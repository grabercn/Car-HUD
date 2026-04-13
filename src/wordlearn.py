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

LEARN_FILE = "/home/chrismslist/northstar/.word_corrections.json"
MAX_ENTRIES = 500


def _load():
    try:
        with open(LEARN_FILE) as f:
            return json.load(f)
    except Exception:
        return {"words": {}, "phrases": {}}


def _save(data):
    try:
        # Trim if too large — keep most-used entries
        if len(data["words"]) > MAX_ENTRIES:
            sorted_w = sorted(data["words"].items(),
                              key=lambda x: -x[1].get("hits", 0))
            data["words"] = dict(sorted_w[:MAX_ENTRIES])
        if len(data["phrases"]) > MAX_ENTRIES:
            sorted_p = sorted(data["phrases"].items(),
                              key=lambda x: -x[1].get("hits", 0))
            data["phrases"] = dict(sorted_p[:MAX_ENTRIES])
        with open(LEARN_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def learn(vosk_text, actual_action, actual_target):
    """Learn from a successful Gemini interpretation.
    Maps misheard words to what they should have been.
    """
    data = _load()
    vosk_words = vosk_text.lower().split()

    # Learn word-level corrections
    # If the target word isn't in what Vosk heard, find the closest misheard word
    target_lower = actual_target.lower()
    if target_lower and target_lower not in vosk_words:
        # Find the word Vosk likely garbled
        # Heuristic: the word closest in position to where the target should be
        # (usually near the end of the sentence)
        for word in reversed(vosk_words):
            # Skip common words
            if word in ("the", "a", "to", "my", "is", "it", "hey", "honda",
                        "can", "you", "what", "change", "show", "make",
                        "set", "turn", "do", "i", "please"):
                continue
            # This word was probably the garbled version of the target
            key = word
            if key not in data["words"]:
                data["words"][key] = {"corrections": {}, "hits": 0}
            corrections = data["words"][key]["corrections"]
            corrections[target_lower] = corrections.get(target_lower, 0) + 1
            data["words"][key]["hits"] += 1
            break

    # Learn phrase-level patterns
    # Map short phrases to actions
    # Remove wake words and common filler
    clean = []
    skip = {"hey", "honda", "hondo", "a", "the", "please", "can", "you",
            "could", "would", "i", "want", "to", "me", "my", "do"}
    for w in vosk_words:
        if w not in skip:
            clean.append(w)
    if clean:
        phrase_key = " ".join(clean[:4])  # first 4 meaningful words
        if phrase_key not in data["phrases"]:
            data["phrases"][phrase_key] = {"corrections": {}, "hits": 0}
        action_key = f"{actual_action}:{actual_target}"
        pc = data["phrases"][phrase_key]["corrections"]
        pc[action_key] = pc.get(action_key, 0) + 1
        data["phrases"][phrase_key]["hits"] += 1

    _save(data)


def correct(text):
    """Apply learned corrections to Vosk text.
    Returns corrected text and confidence (0-1).
    """
    data = _load()
    if not data["words"] and not data["phrases"]:
        return text, 0.0, None

    words = text.lower().split()
    corrected = list(words)
    corrections_made = 0

    # Word-level corrections
    for i, word in enumerate(words):
        if word in data["words"]:
            entry = data["words"][word]
            if entry["corrections"] and entry["hits"] >= 2:
                # Pick the most common correction
                best = max(entry["corrections"].items(), key=lambda x: x[1])
                if best[1] >= 2:  # need at least 2 confirmations
                    corrected[i] = best[0]
                    corrections_made += 1

    corrected_text = " ".join(corrected)

    # Phrase-level: check if we've seen this pattern before
    clean = [w for w in words if w not in
             {"hey", "honda", "hondo", "a", "the", "please", "can", "you",
              "could", "would", "i", "want", "to", "me", "my", "do"}]
    phrase_key = " ".join(clean[:4])

    phrase_action = None
    if phrase_key in data["phrases"]:
        entry = data["phrases"][phrase_key]
        if entry["corrections"] and entry["hits"] >= 2:
            best = max(entry["corrections"].items(), key=lambda x: x[1])
            if best[1] >= 2:
                phrase_action = best[0]  # "action:target"

    confidence = min(1.0, corrections_made * 0.3)
    return corrected_text, confidence, phrase_action


def get_stats():
    """Return learning stats."""
    data = _load()
    return {
        "words_learned": len(data["words"]),
        "phrases_learned": len(data["phrases"]),
        "total_hits": sum(e["hits"] for e in data["words"].values())
    }


# ── Audio parameter reinforcement learning ──
AUDIO_PARAMS_FILE = "/home/chrismslist/northstar/.audio_params.json"

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
VOICE_PROFILE_FILE = "/home/chrismslist/northstar/.voice_profile.json"

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
