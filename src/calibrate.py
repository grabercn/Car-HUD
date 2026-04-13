#!/usr/bin/env python3
"""Voice Calibration Tool — run in the car for real-world tuning.
Press SPACE to start a calibration round. Say "hey honda what's the weather"
clearly 5 times. The system tests different gain levels and picks the best.
Results are saved to .audio_params.json for the voice service.

Run via: keyboard shortcut or "Hey Honda calibrate"
"""

import os
import sys
import json
import time
import struct
import math
import subprocess
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SAMPLE_RATE = 16000
PARAMS_FILE = "/home/chrismslist/northstar/.audio_params.json"
CALIB_DIR = "/tmp/car-hud-calibration"
SIGNAL_FILE = "/tmp/car-hud-calibration-status"


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


_calib_start = 0

def write_status(status, progress=0, detail="", mic="", gain=0, round_num=0, total_rounds=0):
    global _calib_start
    if _calib_start == 0:
        _calib_start = time.time()
    elapsed = time.time() - _calib_start
    eta = ""
    if progress > 5:
        total_est = elapsed / (progress / 100)
        remaining = total_est - elapsed
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        eta = f"{mins}m{secs:02d}s left"
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump({"status": status, "progress": progress,
                       "detail": detail, "mic": mic, "gain": gain,
                       "round": round_num, "total": total_rounds,
                       "eta": eta, "time": time.time()}, f)
    except Exception:
        pass


def find_mics():
    usb = cam = None
    for c in range(6):
        p = f"/proc/asound/card{c}/id"
        if os.path.exists(p):
            with open(p) as f:
                name = f.read().strip()
            if name in ("Audio", "Card"): usb = c
            elif name == "C925e": cam = c
    return usb, cam


def record_sample(card, duration=5):
    """Record from a mic, return raw samples."""
    tmp = f"{CALIB_DIR}/sample_{card}_{int(time.time())}.wav"
    subprocess.run(
        ["arecord", "-D", f"plughw:{card},0", "-d", str(duration),
         "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", tmp],
        capture_output=True, timeout=duration + 5)
    try:
        w = wave.open(tmp)
        frames = w.readframes(w.getnframes())
        samples = struct.unpack(f"<{len(frames)//2}h", frames)
        w.close()
        os.remove(tmp)
        return list(samples)
    except Exception:
        return None


_vosk_model = None

def test_gain(samples, gain):
    """Run Vosk on samples at given gain, return (text, score)."""
    global _vosk_model
    from vosk import Model, KaldiRecognizer

    if _vosk_model is None:
        _vosk_model = Model("/home/chrismslist/northstar/vosk-model")
    rec = KaldiRecognizer(_vosk_model, SAMPLE_RATE)
    rec.SetWords(True)

    # Only test first 8 seconds (contains key phrases, saves CPU)
    max_samples = SAMPLE_RATE * 8
    trimmed = samples[:max_samples]
    boosted = [max(-32767, min(32767, s * gain)) for s in trimmed]
    data = struct.pack(f"<{len(boosted)}h", *boosted)

    texts = []
    for i in range(0, len(data), 4096):
        if rec.AcceptWaveform(data[i:i+4096]):
            t = json.loads(rec.Result()).get("text", "").strip()
            if t: texts.append(t)
    t = json.loads(rec.FinalResult()).get("text", "").strip()
    if t: texts.append(t)

    full = " ".join(texts).lower()

    # Score based on the actual calibration phrases:
    # "hey honda whats the weather"
    # "hey honda change the color to green"
    # "hey honda change the color to red"
    # "hey honda what is 2+2"
    targets = {
        "honda": 4, "hondo": 3,  # wake word (most important)
        "weather": 2,
        "color": 2,
        "green": 2,
        "red": 2, "read": 1,
        "two": 2, "plus": 2,
        "change": 1,
        "what": 1,
    }
    score = sum(weight for word, weight in targets.items() if word in full)

    return full, score


def calibrate(mic_card, mic_name, rounds=2):
    """Run calibration by playing the voice sample through speakers
    and recording what the mic picks up through room acoustics.
    Tests multiple gains to find optimal settings.
    """
    VOICE_SAMPLE = "/tmp/voice_sample.wav"
    if not os.path.exists(VOICE_SAMPLE):
        log(f"  No voice sample at {VOICE_SAMPLE} — skipping")
        return 5, 0

    # Get exact sample duration
    w = wave.open(VOICE_SAMPLE)
    sample_duration = int(w.getnframes() / w.getframerate()) + 2
    w.close()

    # Trim to just "hey honda what's the weather" (first 4 seconds) for fast testing
    TRIMMED = f"{CALIB_DIR}/trimmed.wav"
    subprocess.run(["ffmpeg", "-i", VOICE_SAMPLE, "-t", "4", "-y", TRIMMED],
                   capture_output=True, timeout=10)
    play_file = TRIMMED if os.path.exists(TRIMMED) else VOICE_SAMPLE
    play_duration = 4 if os.path.exists(TRIMMED) else sample_duration

    log(f"Calibrating {mic_name} (card {mic_card}) — {rounds} rounds...")
    write_status("calibrating", 0, f"Calibrating {mic_name}...")

    gain_scores = {}
    gain_texts = {}
    gains = [2, 4, 6, 8]
    for gain in gains:
        gain_scores[gain] = 0
        gain_texts[gain] = []

    total_steps = len(gains) * rounds
    current_step = 0

    for gain in gains:
        for r in range(rounds):
            current_step += 1
            pct = int(((current_step - 1) / total_steps) * 100)
            
            log(f"  Testing gain {gain}x, round {r+1}/{rounds}...")
            write_status("recording", pct, f"Playing sample (Gain {gain}x)...",
                         mic=mic_name, gain=gain, round_num=r+1, total_rounds=rounds)

            # Play voice sample through speaker while recording from mic
            rec_file = f"{CALIB_DIR}/calib_{mic_card}_{gain}_{r}.wav"
            rec_dur = play_duration + 2
            rec_proc = subprocess.Popen(
                ["arecord", "-D", f"plughw:{mic_card},0",
                 "-d", str(rec_dur),
                 "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", rec_file],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.4)

            # Play the trimmed sample
            subprocess.run(["aplay", "-D", "default", play_file],
                           capture_output=True, timeout=play_duration + 5)

            try:
                rec_proc.wait(timeout=rec_dur + 5)
            except subprocess.TimeoutExpired:
                rec_proc.kill()

            # Load and test immediately
            try:
                w = wave.open(rec_file)
                frames = w.readframes(w.getnframes())
                samples = list(struct.unpack(f"<{len(frames)//2}h", frames))
                w.close()
                os.remove(rec_file)
                
                write_status("testing", pct + 2, f"Analyzing {gain}x...",
                             mic=mic_name, gain=gain, round_num=r+1, total_rounds=rounds)
                
                text, score = test_gain(samples, gain)
                gain_scores[gain] += score
                gain_texts[gain].append(text[:80])
                log(f"    round {r+1} score: +{score} '{text[:40]}'")
            except Exception as e:
                log(f"    round {r+1} failed: {e}")

            time.sleep(0.5)

    # Pick best gain
    best_gain = max(gain_scores, key=gain_scores.get)
    best_score = gain_scores[best_gain]

    log(f"\n  === {mic_name} RESULTS ===")
    for gain in sorted(gain_scores):
        marker = " <<<" if gain == best_gain else ""
        log(f"    gain={gain}x: total_score={gain_scores[gain]}{marker}")
        for t in gain_texts[gain][:2]:
            log(f"      '{t}'")
    log(f"  BEST: gain={best_gain}x (score {best_score})")
    return best_gain, best_score


def main():
    os.makedirs(CALIB_DIR, exist_ok=True)

    # Stop voice service and dashcam during calibration to free RAM + mic
    subprocess.run(["sudo", "systemctl", "stop", "car-hud-voice"],
                   capture_output=True, timeout=5)
    subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                   capture_output=True, timeout=5)
    subprocess.run(["pkill", "-f", "ffmpeg.*video"], capture_output=True)
    time.sleep(2)

    # Preload Vosk model once
    global _vosk_model
    from vosk import Model
    log("Loading Vosk model...")
    write_status("loading", 0, "Loading speech model...")
    _vosk_model = Model("/home/chrismslist/northstar/vosk-model")
    log("Model loaded")

    usb_card, cam_card = find_mics()
    log("=== Voice Calibration Tool ===")
    log(f"USB mic: card {usb_card}, CAM mic: card {cam_card}")
    log("Playing voice sample and testing recognition at each gain level")
    log("")

    results = {}

    if usb_card is not None:
        g, s = calibrate(usb_card, "USB-lapel")
        results["mic1_base_gain"] = float(g)

    if cam_card is not None:
        g, s = calibrate(cam_card, "CAM-dash")
        results["mic2_base_gain"] = float(g)

    # Save results
    results["target_speech_rms"] = 5000.0
    results["voice_threshold_mult"] = 2.0
    results["calibrated"] = True
    results["calibrated_time"] = time.strftime("%Y-%m-%d %H:%M")

    with open(PARAMS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    log(f"\nCalibration saved: {results}")
    write_status("done", 100,
                 f"USB={results.get('mic1_base_gain','-')}x  CAM={results.get('mic2_base_gain','-')}x")

    # Play success chime
    subprocess.run(["aplay", "-D", "default",
                   "/home/chrismslist/northstar/chime_ok.wav"],
                   capture_output=True, timeout=3)

    # Restart services with new params
    subprocess.run(["sudo", "systemctl", "start", "car-hud-voice"],
                   capture_output=True, timeout=5)
    subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                   capture_output=True, timeout=5)
    log("Services restarted with calibrated params")


if __name__ == "__main__":
    main()
