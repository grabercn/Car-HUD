#!/usr/bin/env python3
"""Generate radar alert WAV sounds for each band type."""

import struct
import math
import os

INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))

def gen_wav(filename, freq, duration=0.5, volume=0.8, pattern="steady"):
    """Generate a WAV file with specified frequency and pattern."""
    sample_rate = 22050
    n_samples = int(sample_rate * duration)

    samples = []
    for i in range(n_samples):
        t = i / sample_rate

        if pattern == "steady":
            val = math.sin(2 * math.pi * freq * t)
        elif pattern == "chirp":
            # Rising frequency
            f = freq + (freq * 0.5 * t / duration)
            val = math.sin(2 * math.pi * f * t)
        elif pattern == "pulse":
            # On/off pulsing
            if int(t * 8) % 2 == 0:
                val = math.sin(2 * math.pi * freq * t)
            else:
                val = 0
        elif pattern == "urgent":
            # Fast alternating two tones
            if int(t * 12) % 2 == 0:
                val = math.sin(2 * math.pi * freq * t)
            else:
                val = math.sin(2 * math.pi * (freq * 1.5) * t)
        elif pattern == "laser":
            # Rapid high-pitched beeps
            if int(t * 20) % 2 == 0:
                val = math.sin(2 * math.pi * freq * t)
            else:
                val = 0

        # Fade in/out
        env = 1.0
        if t < 0.02:
            env = t / 0.02
        elif t > duration - 0.02:
            env = (duration - t) / 0.02

        val = int(val * volume * env * 32767)
        val = max(-32768, min(32767, val))
        samples.append(val)

    # Write WAV
    data = struct.pack(f"<{len(samples)}h", *samples)
    with open(filename, "wb") as f:
        # WAV header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + len(data)))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", len(data)))
        f.write(data)

    print(f"Generated: {filename}")


if __name__ == "__main__":
    sounds = {
        "radar_x.wav": (800, 0.4, "steady"),
        "radar_k.wav": (1200, 0.4, "chirp"),
        "radar_ka.wav": (1600, 0.5, "urgent"),
        "radar_laser.wav": (2400, 0.3, "laser"),
        "radar_alert.wav": (1000, 0.5, "pulse"),
    }
    for fname, (freq, dur, pat) in sounds.items():
        gen_wav(os.path.join(INSTALL_DIR, fname), freq, dur, 0.7, pat)
    print("All radar sounds generated!")
