#!/usr/bin/env python3
"""Honda Accord Voice System
Vosk STT + dual threaded mics + auto-gain + Gemini NLU.
Wordlearn + response caching + reinforcement learning.
"""

import os
import sys
import json
import time
import struct
import math
import subprocess
import threading
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import process_command, smart_tts
from wordlearn import reinforce_audio, update_voice_profile, load_audio_params
from vosk import Model, KaldiRecognizer

SIGNAL_FILE = "/tmp/car-hud-voice-signal"
VOSK_MODEL = "/home/chrismslist/northstar/vosk-model"
LOG_FILE = "/tmp/car-hud-voice.log"
SAMPLE_RATE = 16000
CHUNK = 1024  # 64ms — faster wake detection

# Wake word detection
_HONDA_LIKE = {"honda", "hondo", "handa", "hundred", "hunter", "honor",
               "onda", "conda", "harder", "hotter", "hodna", "hone",
               "hunger", "wander", "ponder", "rhonda", "fonda", "ronda",
               "kinda", "wonder", "under", "thunder", "handle", "handled",
               "handful", "handy", "haunted", "hounded", "founded",
               "wanted", "hunted", "bonded", "pondered", "wandered",
               "wondered", "blunder", "plunder", "yonder", "handed"}
_HEY_LIKE = {"hey", "hay", "he", "they", "say", "day", "yeah", "yay",
             "hi", "harry", "gee", "key", "okay", "away"}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 50000:
            with open(LOG_FILE, "r") as rf:
                lines = rf.readlines()[-100:]
            with open(LOG_FILE, "w") as wf:
                wf.writelines(lines)
    except Exception:
        pass


def signal_hud(action, target, raw_text="", extra=None):
    data = {"action": action, "target": target, "raw": raw_text, "time": time.time()}
    if extra:
        data.update(extra)
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# Sound output — auto-detect USB audio card, fall back to default
_sound_dev = None
def play_sound(path):
    global _sound_dev
    if _sound_dev is None:
        for c in range(6):
            p = f"/proc/asound/card{c}/id"
            if os.path.exists(p):
                with open(p) as f:
                    if f.read().strip() in ("Audio", "Card"):
                        _sound_dev = f"dmix:{c}"
                        break
        if _sound_dev is None:
            _sound_dev = "default"
    try:
        subprocess.Popen(["aplay", "-D", _sound_dev, path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

def play_wake(): play_sound("/home/chrismslist/northstar/chime_wake.wav")
def play_ok(): play_sound("/home/chrismslist/northstar/chime_ok.wav")
def play_err(): play_sound("/home/chrismslist/northstar/chime_err.wav")
def speak(text): smart_tts(text)


# Wake word
def _sounds_like_honda(w):
    w = w.lower()
    if w in _HONDA_LIKE: return True
    if len(w) < 4 or len(w) > 9: return False
    if w.startswith(("hond", "hund", "hont", "hand", "haun", "houn")): return True
    if w.startswith(("hon", "hun", "han")) and len(w) >= 5: return True
    return False

def check_wake_word(text):
    words = text.lower().split()
    for w in words:
        if w in ("honda", "hondo"): return True
    for i in range(len(words) - 1):
        if words[i] in _HEY_LIKE and _sounds_like_honda(words[i + 1]): return True
    if len(words) >= 2:
        for w in words:
            if _sounds_like_honda(w): return True
    return False


# Threaded mic reader
class MicReader:
    def __init__(self, card, name, gain=8.0):
        self.card = card
        self.name = name
        self.gain = gain
        self.rms = 0.0
        self.alive = False
        self._buf = b""
        self._lock = threading.Lock()

    def start(self):
        self.alive = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        noise_floor = 200.0
        while self.alive:
            try:
                proc = subprocess.Popen(
                    ["arecord", "-D", f"plughw:{self.card},0",
                     "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                while self.alive:
                    raw = proc.stdout.read(CHUNK * 2)
                    if not raw: break

                    samps = struct.unpack(f"<{len(raw)//2}h", raw)
                    raw_rms = math.sqrt(sum(s*s for s in samps[:100]) / 100)

                    # Adaptive gain per frame
                    if raw_rms < noise_floor * 1.5:
                        noise_floor = noise_floor * 0.95 + raw_rms * 0.05
                    elif raw_rms > noise_floor * 2.5:
                        # Voice detected — adapt gain toward target
                        current_out = raw_rms * self.gain
                        if current_out > 0:
                            ratio = 4000.0 / current_out
                            self.gain = self.gain * 0.92 + (self.gain * ratio) * 0.08
                            self.gain = max(1.0, min(8.0, self.gain))  # adaptive, capped at 8x

                    g = int(self.gain)
                    boosted = struct.pack(f"<{len(samps)}h",
                        *[max(-32767, min(32767, s * g)) for s in samps])
                    bsamps = struct.unpack(f"<{len(boosted)//2}h", boosted)
                    self.rms = math.sqrt(sum(s*s for s in bsamps[:100]) / 100)

                    with self._lock:
                        self._buf += boosted
                        if len(self._buf) > CHUNK * 2 * 15:
                            self._buf = self._buf[-(CHUNK * 2 * 8):]
                proc.kill()
            except Exception:
                pass
            time.sleep(1)

    def read(self, n):
        with self._lock:
            if len(self._buf) >= n:
                d = self._buf[:n]
                self._buf = self._buf[n:]
                return d
        return None

    def stop(self):
        self.alive = False


def find_mics():
    usb = cam = None
    for c in range(6):
        p = f"/proc/asound/card{c}/id"
        if os.path.exists(p):
            with open(p) as f:
                n = f.read().strip()
            if n in ("Audio", "Card"): usb = c
            elif n == "C925e": cam = c
    return usb, cam


def main():
    log("Loading Vosk model...")
    model = Model(VOSK_MODEL)
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)
    # Increase max alternatives for better accuracy
    rec.SetMaxAlternatives(3)
    log("Vosk ready (single recognizer, 3 alternatives)")

    params = load_audio_params()
    # Training: optimal RMS ~4000. USB mic raw ~360, CAM ~1100
    # So USB needs ~5x, CAM needs ~2x. Cap at 8x to prevent distortion.
    gain1 = min(8.0, max(1.0, params.get("mic1_base_gain", 5.0)))
    gain2 = min(8.0, max(1.0, params.get("mic2_base_gain", 2.0)))

    # Dynamic gain: starts at learned value, adapts each frame
    # Tracks noise floor per mic and adjusts gain to keep speech at target RMS
    target_rms = 4000.0
    noise1 = 200.0
    noise2 = 200.0
    log(f"Gains: usb={gain1:.0f}x cam={gain2:.0f}x (adaptive)")

    usb_card, cam_card = find_mics()
    mics = []
    if usb_card is not None:
        m = MicReader(usb_card, "USB", gain1)
        m.start()
        mics.append(m)
        log(f"Mic: USB card {usb_card} ({gain1:.0f}x)")
    if cam_card is not None:
        m = MicReader(cam_card, "CAM", gain2)
        m.start()
        mics.append(m)
        log(f"Mic: CAM card {cam_card} ({gain2:.0f}x)")
    if not mics:
        log("No mics!")
        return

    log(f"Listening for 'Hey Honda'... ({len(mics)} mic(s))")
    signal_hud("status", "listening")

    awaiting = False
    cmd_timeout = 0
    wake_chimed = False
    frames = 0
    nbytes = CHUNK * 2
    # Accumulate text after wake word to catch full sentences
    accumulated_text = ""
    accumulate_timeout = 0

    def execute(cmd, text):
        reply = cmd.get("reply", "")
        source = cmd.get("source", "local")
        if reply: speak(reply)
        signal_hud(cmd["action"], cmd["target"], text,
                   extra={"reply": reply, "source": source})

    def process_text(text):
        """Handle recognized text — wake detection + command processing."""
        nonlocal awaiting, cmd_timeout, wake_chimed
        is_wake = check_wake_word(text)

        try:
            with open("/tmp/car-hud-transcript", "w") as f:
                json.dump({"text": text, "wake": is_wake or awaiting,
                            "time": time.time()}, f)
        except Exception: pass

        if is_wake or awaiting:
            action, target, reply, source = process_command(text)
            if action != "unknown":
                cmd = {"action": action, "target": target,
                       "reply": reply, "source": source}
                log(f"Command [{source}]: {action}->{target}")
                play_ok()
                execute(cmd, text)
                reinforce_audio(True, gain1, gain2, 0, 0)
                update_voice_profile(0)
                awaiting = False
                return True
            elif is_wake:
                # Wake detected — stay listening for command
                if not wake_chimed: play_wake()
                awaiting = True
                cmd_timeout = time.time() + 10
                log(f"Wake: '{text}'")
                signal_hud("wake", "listening")
            elif awaiting:
                # Got text while awaiting command — don't close yet
                # The accumulator will handle it
                cmd_timeout = time.time() + 6
                signal_hud("wake", "listening")
        return False

    try:
        while True:
            # Read from each mic independently
            d1 = mics[0].read(nbytes) if len(mics) > 0 else None
            d2 = mics[1].read(nbytes) if len(mics) > 1 else None
            m1_rms = mics[0].rms if len(mics) > 0 else 0
            m2_rms = mics[1].rms if len(mics) > 1 else 0

            if not d1 and not d2:
                time.sleep(0.01)
                continue

            # Mic levels for HUD
            frames += 1
            if frames % 3 == 0:
                try:
                    with open("/tmp/car-hud-mic-level", "w") as f:
                        f.write(f"{min(1,m1_rms/6000):.3f},{min(1,m2_rms/6000):.3f}")
                except Exception: pass

            # Pick loudest mic's audio for this frame
            best = None
            if d1 and d2:
                best = d1 if mics[0].rms > mics[1].rms else d2
            elif d1:
                best = d1
            elif d2:
                best = d2

            if not best:
                continue

            # Single recognizer — feed best audio
            text = ""
            partial_text = ""
            if rec.AcceptWaveform(best):
                result = json.loads(rec.Result())
                # Check alternatives for better wake word detection
                alts = result.get("alternatives", [])
                if alts:
                    # Pick the alternative that contains honda-like words
                    best_alt = alts[0].get("text", "").strip()
                    for alt in alts:
                        t = alt.get("text", "")
                        if check_wake_word(t):
                            best_alt = t.strip()
                            break
                    text = best_alt
                else:
                    text = result.get("text", "").strip()
            else:
                partial_text = json.loads(rec.PartialResult()).get("partial", "")

            if text:
                wake_chimed = False
                log(f"Heard: '{text}'")

                if awaiting:
                    # After wake: accumulate fragments until silence
                    accumulated_text = (accumulated_text + " " + text).strip()
                    accumulate_timeout = time.time() + 3.0  # wait 3s for complete sentence
                elif check_wake_word(text):
                    # Wake word in this text — check if command is also in it
                    accumulated_text = text
                    process_text(text)
                    if awaiting:
                        accumulate_timeout = time.time() + 1.5
                else:
                    process_text(text)

            # Flush accumulated text after timeout — this is our best shot
            if accumulated_text and accumulate_timeout and time.time() > accumulate_timeout:
                log(f"Accumulated: '{accumulated_text}'")
                result = process_text(accumulated_text)
                if not result:
                    # Command failed — still try, Gemini might understand
                    log(f"Retrying with Gemini...")
                    action, target, reply, source = process_command(accumulated_text)
                    if action != "unknown":
                        cmd = {"action": action, "target": target,
                               "reply": reply, "source": source}
                        play_ok()
                        execute(cmd, accumulated_text)
                    else:
                        play_err()
                        signal_hud("status", "timeout")
                awaiting = False
                accumulated_text = ""
                accumulate_timeout = 0

            # Partials — check for wake word
            pt = partial_text
            if pt:
                try:
                    with open("/tmp/car-hud-transcript", "w") as f:
                        json.dump({"partial": pt, "wake": awaiting,
                                    "time": time.time()}, f)
                except Exception: pass
                if not awaiting and not wake_chimed and check_wake_word(pt):
                    play_wake()
                    wake_chimed = True
                    awaiting = True
                    cmd_timeout = time.time() + 10
                    log(f"Wake (partial): '{pt}'")
                    signal_hud("wake", "listening")

            if awaiting and time.time() > cmd_timeout:
                awaiting = False
                signal_hud("status", "timeout")

    except KeyboardInterrupt:
        log("Stopped.")
    finally:
        for m in mics: m.stop()


if __name__ == "__main__":
    main()
