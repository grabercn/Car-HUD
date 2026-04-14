#!/usr/bin/env python3
"""Car-HUD Audio Controller
Single service managing ALL audio routing.
Every other service calls this instead of aplay directly.

Output priority: USB audio card > HDMI > Pi headphones
Input priority: USB mic > Webcam mic

Features:
- Auto-detects available devices, re-scans every 30s
- Plays sounds via play(filepath)
- Speaks text via speak(text)
- Provides mic device info for voice service
- Writes status to /tmp/car-hud-audio-status

Usage from other services:
    import sys; sys.path.insert(0, "/home/chrismslist/car-hud")
    from audio_controller import play, speak, get_output_device, get_mic_devices
"""

import os
import sys
import time
import json
import subprocess
import threading

INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = "/tmp/car-hud-audio-status"

# Device cache
_output_dev = None
_mic_devs = []
_last_scan = 0
_scan_lock = threading.Lock()
SCAN_INTERVAL = 30


def _scan_devices():
    """Scan all audio devices, pick best output and inputs."""
    global _output_dev, _mic_devs, _last_scan

    with _scan_lock:
        if time.time() - _last_scan < SCAN_INTERVAL and _output_dev:
            return

        outputs = []
        inputs = []

        for card in range(8):
            id_path = f"/proc/asound/card{card}/id"
            if not os.path.exists(id_path):
                continue
            with open(id_path) as f:
                name = f.read().strip()

            # Check if it has playback
            pcm_path = f"/proc/asound/card{card}/pcm0p"
            has_playback = os.path.exists(pcm_path) or os.path.exists(f"/proc/asound/card{card}/pcm0p/info")

            # Check if it has capture
            pcm_cap = f"/proc/asound/card{card}/pcm0c"
            has_capture = os.path.exists(pcm_cap) or os.path.exists(f"/proc/asound/card{card}/pcm0c/info")

            if has_playback or name in ("Headphones", "vc4hdmi", "Audio", "Card"):
                hdmi_connected = False
                if name == "vc4hdmi":
                    try:
                        with open("/sys/class/drm/card0-HDMI-A-1/status") as f:
                            hdmi_connected = "connected" in f.read()
                    except Exception:
                        pass

                priority = 0
                if name in ("Audio", "Card"):
                    priority = 100  # USB audio card — highest
                    dev = f"dmix:{card}"  # allows simultaneous record+play
                elif name == "vc4hdmi" and hdmi_connected:
                    priority = 80  # HDMI — second
                    dev = f"plughw:{card},0"
                elif name == "Headphones":
                    priority = 50  # Pi headphones — fallback
                    dev = f"plughw:{card},0"
                else:
                    priority = 10
                    dev = f"plughw:{card},0"

                outputs.append({"card": card, "name": name, "dev": dev, "priority": priority})

            if has_capture or name in ("Audio", "Card", "C925e"):
                mic_type = "unknown"
                if name in ("Audio", "Card"):
                    mic_type = "usb"
                elif name == "C925e":
                    mic_type = "webcam"

                inputs.append({"card": card, "name": name, "type": mic_type,
                               "dev": f"plughw:{card},0"})

        # Sort by priority (highest first)
        outputs.sort(key=lambda x: -x["priority"])
        _output_dev = outputs[0]["dev"] if outputs else "default"
        _mic_devs = inputs

        _last_scan = time.time()

        # Write status
        try:
            status = {
                "output": _output_dev,
                "output_name": outputs[0]["name"] if outputs else "none",
                "mics": [{"card": m["card"], "name": m["name"], "type": m["type"]} for m in _mic_devs],
                "timestamp": time.time()
            }
            with open(STATUS_FILE, "w") as f:
                json.dump(status, f)
        except Exception:
            pass


def get_output_device():
    """Get the best audio output device string for aplay -D."""
    _scan_devices()
    return _output_dev


def get_mic_devices():
    """Get list of mic devices [{card, name, type, dev}]."""
    _scan_devices()
    return list(_mic_devs)


def play(filepath):
    """Play a WAV file on the best available output. Non-blocking."""
    if not os.path.exists(filepath):
        return
    dev = get_output_device()
    try:
        subprocess.Popen(["aplay", "-D", dev, "-q", filepath],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def speak(text, voice="en-us+f3", speed=145):
    """Speak text via espeak → ffmpeg → best output. Non-blocking."""
    dev = get_output_device()
    try:
        subprocess.Popen(
            f'espeak -v {voice} -s {speed} -p 60 -a 180 --stdout "{text}" | '
            f'ffmpeg -i - -ar 48000 -ac 2 -f wav - 2>/dev/null | '
            f'aplay -D {dev} -q 2>/dev/null',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def play_chime(name):
    """Play a named chime (wake, ok, err, wifi, startup, etc.)."""
    path = os.path.join(INSTALL_DIR, f"chime_{name}.wav")
    play(path)


# Convenience functions
def chime_wake(): play_chime("wake")
def chime_ok(): play_chime("ok")
def chime_err(): play_chime("err")
def chime_wifi(): play_chime("wifi")
def chime_startup(): play_chime("startup")
def chime_obd(): play_chime("obd")
def chime_rec(): play_chime("rec")


if __name__ == "__main__":
    # Self-test
    _scan_devices()
    print(f"Output: {_output_dev}")
    print(f"Mics: {_mic_devs}")
    print("Playing startup chime...")
    chime_startup()
    time.sleep(2)
    print("Speaking...")
    speak("Audio controller online")
    time.sleep(3)
    print("Done")
