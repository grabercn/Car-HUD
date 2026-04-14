#!/usr/bin/env python3
"""Generate all Car-HUD sound effects.
Honda-inspired chimes — warm, clean, professional.
All files: stereo, 48kHz, S16_LE WAV.
"""

import wave
import struct
import math
import os

RATE = 48000
INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))


def make_wav(filename, frames):
    path = os.path.join(INSTALL_DIR, filename)
    w = wave.open(path, "w")
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(b"".join(frames))
    w.close()
    print(f"  {filename}")


def tone(freq, duration, amplitude=0.5, attack=0.01, decay=4):
    """Single tone with envelope."""
    frames = []
    for i in range(int(RATE * duration)):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-t * decay)
        s = math.sin(2 * math.pi * freq * t) * amplitude
        sample = max(-32767, min(32767, int(s * env * 28000)))
        frames.append(struct.pack("<hh", sample, sample))
    return frames


def silence(duration):
    return [struct.pack("<hh", 0, 0) for _ in range(int(RATE * duration))]


def main():
    print("Generating Car-HUD sounds...")

    # Wake chime — warm two-note (E5+A5), heard when "Hey Honda" detected
    make_wav("chime_wake.wav",
             tone(659, 0.5, 0.5, 0.01, 4) +  # E5
             [struct.pack("<hh", 0, 0)] * int(RATE * 0.02))

    # OK/success — quick ascending C5→E5→G5
    frames = []
    for freq, dur in [(523, 0.1), (659, 0.1), (784, 0.15)]:
        frames += tone(freq, dur, 0.4, 0.005, 6)
        frames += silence(0.02)
    make_wav("chime_ok.wav", frames)

    # Error — descending G4→E4, slightly buzzy
    frames = tone(392, 0.15, 0.4, 0.005, 4) + silence(0.02) + tone(330, 0.2, 0.4, 0.005, 3)
    make_wav("chime_err.wav", frames)

    # WiFi connected — bright rising arpeggio C6→E6→G6
    frames = []
    for freq, dur in [(1047, 0.08), (1319, 0.08), (1568, 0.12)]:
        frames += tone(freq, dur, 0.4, 0.005, 8)
        frames += silence(0.015)
    make_wav("chime_wifi.wav", frames)

    # Think/processing — soft single A4 pulse
    make_wav("chime_think.wav", tone(440, 0.3, 0.3, 0.01, 5))

    # Startup — warm ascending chord E4→A4→C#5→E5
    frames = []
    for freq, dur in [(330, 0.12), (440, 0.12), (554, 0.12), (659, 0.2)]:
        frames += tone(freq, dur, 0.35, 0.008, 5)
        frames += silence(0.03)
    make_wav("chime_startup.wav", frames)

    # Shutdown — descending E5→C#5→A4→E4
    frames = []
    for freq, dur in [(659, 0.12), (554, 0.12), (440, 0.12), (330, 0.25)]:
        frames += tone(freq, dur, 0.3, 0.008, 4)
        frames += silence(0.03)
    make_wav("chime_shutdown.wav", frames)

    # Update available — two quick pings
    frames = tone(880, 0.08, 0.3, 0.003, 8) + silence(0.1) + tone(880, 0.08, 0.3, 0.003, 8)
    make_wav("chime_update.wav", frames)

    # OBD connected — low confident double-tap
    frames = tone(523, 0.1, 0.35, 0.005, 6) + silence(0.05) + tone(659, 0.12, 0.35, 0.005, 6)
    make_wav("chime_obd.wav", frames)

    # Camera recording start — single click
    make_wav("chime_rec.wav", tone(1200, 0.05, 0.3, 0.002, 15))

    print("All sounds generated.")


if __name__ == "__main__":
    main()
