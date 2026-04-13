#!/usr/bin/env python3
"""Honda Accord Dashcam Service
Records from webcam in 5-min chunks. Auto-records when driving (OBD speed > 0).
Voice commands: start/stop recording, preview camera.
Writes status to /tmp/car-hud-dashcam-data.
"""

import os
import sys
import json
import time
import subprocess
import glob

RECORD_DIR = "/home/chrismslist/northstar/dashcam"
SIGNAL_FILE = "/tmp/car-hud-dashcam-data"
VOICE_FILE = "/tmp/car-hud-voice-signal"
OBD_FILE = "/tmp/car-hud-obd-data"
LOG_FILE = "/tmp/car-hud-dashcam.log"
CHUNK_SECONDS = 300
MAX_CHUNKS = 12
VIDEO_DEV = "/dev/video0"


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def write_status(recording, chunks=0, size_mb=0, mode="auto"):
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump({"recording": recording, "chunks": chunks,
                       "size_mb": round(size_mb, 1), "mode": mode,
                       "timestamp": time.time()}, f)
    except Exception:
        pass


def rotate_chunks():
    files = sorted(glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")))
    while len(files) > MAX_CHUNKS:
        oldest = files.pop(0)
        try:
            os.remove(oldest)
            log(f"Rotated: {os.path.basename(oldest)}")
        except Exception:
            pass


def get_total_size_mb():
    total = 0
    for f in glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")):
        total += os.path.getsize(f)
    return total / (1024 * 1024)


def is_driving():
    """Check OBD data — driving if speed > 0."""
    try:
        with open(OBD_FILE) as f:
            data = json.load(f)
            if data.get("connected") and time.time() - data.get("timestamp", 0) < 15:
                speed = data.get("data", {}).get("SPEED", 0)
                return speed is not None and speed > 0
    except Exception:
        pass
    return False


def check_voice_command():
    """Check for dashcam voice commands."""
    try:
        with open(VOICE_FILE) as f:
            data = json.load(f)
            if time.time() - data.get("time", 0) > 5:
                return None
            action = data.get("action", "")
            target = data.get("target", "")
            raw = data.get("raw", "").lower()

            if action == "show" and target == "camera":
                return "preview"
            if "start" in raw and ("record" in raw or "camera" in raw or "dashcam" in raw):
                return "start"
            if "stop" in raw and ("record" in raw or "camera" in raw or "dashcam" in raw):
                return "stop"
    except Exception:
        pass
    return None


def main():
    os.makedirs(RECORD_DIR, exist_ok=True)
    log("Dashcam service starting...")

    if not os.path.exists(VIDEO_DEV):
        log(f"No webcam at {VIDEO_DEV}")
        write_status(False, mode="no camera")
        time.sleep(30)
        return

    manual_override = None  # None=auto, "on"=force record, "off"=force stop
    last_voice_check = 0

    while True:
        # Check voice commands
        now = time.time()
        if now - last_voice_check > 2:
            last_voice_check = now
            cmd = check_voice_command()
            if cmd == "start":
                manual_override = "on"
                log("Voice: manual recording ON")
            elif cmd == "stop":
                manual_override = "off"
                log("Voice: manual recording OFF")
            elif cmd == "preview":
                # Preview handled by HUD — just note it
                pass

        # Decide whether to record
        driving = is_driving()
        should_record = False

        if manual_override == "on":
            should_record = True
            mode = "manual"
        elif manual_override == "off":
            should_record = False
            mode = "stopped"
        elif driving:
            should_record = True
            mode = "driving"
            manual_override = None  # clear manual when auto kicks in
        else:
            # Not driving, no manual override — check if OBD is even connected
            # If no OBD, default to recording (we don't know if we're driving)
            try:
                with open(OBD_FILE) as f:
                    obd = json.load(f)
                    if not obd.get("connected"):
                        should_record = True  # no OBD = always record
                        mode = "auto"
                    else:
                        should_record = False
                        mode = "parked"
            except Exception:
                should_record = True  # no OBD data = always record
                mode = "auto"

        if not should_record:
            chunks = len(glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")))
            write_status(False, chunks, get_total_size_mb(), mode)
            time.sleep(5)
            continue

        # Record a chunk
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output = os.path.join(RECORD_DIR, f"chunk_{timestamp}.mp4")
        chunks = len(glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")))
        write_status(True, chunks, get_total_size_mb(), mode)
        log(f"Recording: {os.path.basename(output)} ({mode})")

        try:
            proc = subprocess.run([
                "ffmpeg", "-f", "v4l2",
                "-video_size", "640x480", "-framerate", "10",
                "-i", VIDEO_DEV,
                "-t", str(CHUNK_SECONDS),
                "-c:v", "h264_v4l2m2m", "-b:v", "500k",
                "-an", "-y", output
            ], capture_output=True, timeout=CHUNK_SECONDS + 30)

            if proc.returncode != 0:
                subprocess.run([
                    "ffmpeg", "-f", "v4l2",
                    "-video_size", "640x480", "-framerate", "5",
                    "-i", VIDEO_DEV,
                    "-t", str(CHUNK_SECONDS),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "28", "-an", "-y", output
                ], capture_output=True, timeout=CHUNK_SECONDS + 30)
        except subprocess.TimeoutExpired:
            log("Recording timeout")
        except Exception as e:
            log(f"Recording error: {e}")
            time.sleep(10)
            continue

        rotate_chunks()
        log(f"Chunk done. {mode}")


if __name__ == "__main__":
    main()
