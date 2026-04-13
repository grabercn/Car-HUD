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
PARAMS_FILE = "/home/chrismslist/car-hud/.audio_params.json"
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
    """Run Vosk on samples at given gain, return (text, score, snr)."""
    global _vosk_model
    from vosk import Model, KaldiRecognizer

    if _vosk_model is None:
        _vosk_model = Model("/home/chrismslist/car-hud/vosk-model")
    rec = KaldiRecognizer(_vosk_model, SAMPLE_RATE)
    rec.SetWords(True)

    # Boost and clip
    max_samples = SAMPLE_RATE * 8
    trimmed = samples[:max_samples]
    
    # Calculate raw RMS and SNR before boost
    raw_rms = math.sqrt(sum(s*s for s in trimmed[:1000]) / 1000)
    speech_rms = math.sqrt(sum(s*s for s in trimmed) / len(trimmed))
    snr = speech_rms / max(1.0, raw_rms)

    boosted = [max(-32767, min(32767, int(s * gain))) for s in trimmed]
    data = struct.pack(f"<{len(boosted)}h", *boosted)

    texts = []
    for i in range(0, len(data), 4096):
        if rec.AcceptWaveform(data[i:i+4096]):
            t = json.loads(rec.Result()).get("text", "").strip()
            if t: texts.append(t)
    t = json.loads(rec.FinalResult()).get("text", "").strip()
    if t: texts.append(t)

    full = " ".join(texts).lower()

    targets = {
        "honda": 5, "hondo": 4, "hundred": 2, "hunter": 2,
        "weather": 3, "color": 3, "green": 3, "red": 3,
        "two": 2, "plus": 2, "what": 1, "change": 1
    }
    score = sum(weight for word, weight in targets.items() if word in full)

    return full, score, snr


def calibrate(mic_card, mic_name, rounds=2):
    VOICE_SAMPLE = "/tmp/voice_sample.wav"
    if not os.path.exists(VOICE_SAMPLE):
        # Create a basic sample if missing? No, user should have it
        log(f"  No voice sample at {VOICE_SAMPLE}")
        return 5.0, 0

    log(f"Calibrating {mic_name} (card {mic_card})...")
    write_status("calibrating", 0, f"Initializing {mic_name}...")

    gain_results = {}
    gains = [2.0, 4.0, 6.0, 8.0, 10.0]
    total_steps = len(gains) * rounds
    current_step = 0

    for gain in gains:
        gain_results[gain] = {"scores": [], "snrs": [], "texts": []}
        for r in range(rounds):
            current_step += 1
            pct = int(((current_step - 1) / total_steps) * 100)
            
            write_status("recording", pct, f"Testing {gain}x (Round {r+1})...",
                         mic=mic_name, gain=gain, round_num=r+1, total_rounds=rounds)

            samples = record_sample(mic_card, duration=5)
            if not samples:
                continue

            write_status("testing", pct + 2, f"Analyzing {gain}x...",
                         mic=mic_name, gain=gain, round_num=r+1, total_rounds=rounds)
            
            text, score, snr = test_gain(samples, gain)
            gain_results[gain]["scores"].append(score)
            gain_results[gain]["snrs"].append(snr)
            gain_results[gain]["texts"].append(text)
            log(f"    {gain}x R{r+1}: score={score} snr={snr:.1f} '{text[:30]}'")

    # Calculate averages and pick best
    best_gain = 5.0
    max_avg_score = -1
    
    for gain, data in gain_results.items():
        if not data["scores"]: continue
        avg_score = sum(data["scores"]) / len(data["scores"])
        avg_snr = sum(data["snrs"]) / len(data["snrs"])
        
        # We want high score, but also decent SNR (not over-boosted noise)
        if avg_score > max_avg_score:
            max_avg_score = avg_score
            best_gain = gain
        elif avg_score == max_avg_score and max_avg_score > 0:
            # Tie breaker: lower gain is better (less distortion)
            pass

    log(f"  Result for {mic_name}: {best_gain}x (Avg Score: {max_avg_score:.1f})")
    return best_gain, max_avg_score


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
    _vosk_model = Model("/home/chrismslist/car-hud/vosk-model")
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
                   "/home/chrismslist/car-hud/chime_ok.wav"],
                   capture_output=True, timeout=3)

    # Restart services with new params
    subprocess.run(["sudo", "systemctl", "start", "car-hud-voice"],
                   capture_output=True, timeout=5)
    subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                   capture_output=True, timeout=5)
    log("Services restarted with calibrated params")


if __name__ == "__main__":
    main()
