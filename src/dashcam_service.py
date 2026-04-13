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
import threading

RECORD_DIR = "/home/chrismslist/car-hud/dashcam"
SIGNAL_FILE = "/tmp/car-hud-dashcam-data"
VOICE_FILE = "/tmp/car-hud-voice-signal"
OBD_FILE = "/tmp/car-hud-obd-data"
LOG_FILE = "/tmp/car-hud-dashcam.log"
CHUNK_SECONDS = 300   # 5 min per chunk
MAX_SIZE_MB = 4096    # Increased to 4GB for dual cams
MAX_CHUNKS = 100       # Increased for dual cams


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_status(recording, chunks=0, size_mb=0, mode="auto", cam_count=0):
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump({"recording": recording, "chunks": chunks,
                       "size_mb": round(size_mb, 1), "mode": mode,
                       "cam_count": cam_count,
                       "timestamp": time.time()}, f)
    except Exception:
        pass


def find_cameras():
    """Find all valid USB video capture devices."""
    cams = []
    try:
        r = subprocess.run(["v4l2-ctl", "--list-devices"], 
                           capture_output=True, text=True, timeout=5)
        lines = r.stdout.split("\n")
        current_bus = ""
        for line in lines:
            if ":" in line and not line.startswith("\t"):
                current_bus = line.lower()
            elif line.strip().startswith("/dev/video"):
                dev = line.strip()
                # Skip internal Pi ISP/Codec/Unicam nodes
                if "bcm2835" in current_bus or "unicam" in current_bus:
                    continue
                # Real capture devices have 0x04200001 caps (Capture + Streaming)
                res = subprocess.run(["v4l2-ctl", "--device", dev, "--all"], 
                                      capture_output=True, text=True, timeout=2)
                if "Device Caps      : 0x04200001" in res.stdout:
                    cams.append(dev)
    except Exception:
        pass
    return sorted(list(set(cams)))


def record_from_cam(cam_dev, output, duration):
    """Record a single chunk from one camera."""
    try:
        # Try hardware encoder first
        cmd = [
            "ffmpeg", "-f", "v4l2",
            "-video_size", "640x480", "-framerate", "10",
            "-i", cam_dev,
            "-t", str(duration),
            "-c:v", "h264_v4l2m2m", "-b:v", "500k",
            "-an", "-y", output
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=duration + 30)
        
        if proc.returncode != 0:
            # Fallback to software encoder
            cmd[9] = "5" # lower framerate
            cmd[12] = "libx264"
            cmd[13] = "-preset"
            cmd.insert(14, "ultrafast")
            cmd.insert(15, "-crf")
            cmd.insert(16, "28")
            subprocess.run(cmd, capture_output=True, timeout=duration + 30)
    except Exception as e:
        log(f"Error recording {cam_dev}: {e}")

def rotate_chunks():
    # ... (unchanged)
    files = sorted(glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")))
    total_mb = get_total_size_mb()
    while len(files) > MAX_CHUNKS or total_mb > MAX_SIZE_MB:
        if not files:
            break
        oldest = files.pop(0)
        try:
            total_mb -= os.path.getsize(oldest) / (1024 * 1024)
            os.remove(oldest)
            log(f"Rotated: {os.path.basename(oldest)} ({total_mb:.0f}MB remaining)")
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

        # Decide whether to record
        driving = is_driving()
        should_record = False
        mode = "auto"

        if manual_override == "on":
            should_record = True
            mode = "manual"
        elif manual_override == "off":
            should_record = False
            mode = "stopped"
        elif driving:
            should_record = True
            mode = "driving"
            manual_override = None
        else:
            try:
                with open(OBD_FILE) as f:
                    obd = json.load(f)
                    if not obd.get("connected"):
                        should_record = True
                        mode = "auto"
                    else:
                        should_record = False
                        mode = "parked"
            except Exception:
                should_record = True
                mode = "auto"

        cams = find_cameras()
        cam_count = len(cams)

        if not should_record or cam_count == 0:
            chunks = len(glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")))
            write_status(False, chunks, get_total_size_mb(), mode, cam_count)
            time.sleep(5)
            continue

        # Record a chunk from each camera in parallel
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        chunks = len(glob.glob(os.path.join(RECORD_DIR, "chunk_*.mp4")))
        write_status(True, chunks, get_total_size_mb(), mode, cam_count)
        
        log(f"Recording {cam_count} cam(s) for {CHUNK_SECONDS}s ({mode})")
        
        threads = []
        for i, cam in enumerate(cams):
            output = os.path.join(RECORD_DIR, f"chunk_{timestamp}_cam{i}.mp4")
            t = threading.Thread(target=record_from_cam, args=(cam, output, CHUNK_SECONDS))
            t.start()
            threads.append(t)
            
        # Wait for all to finish
        for t in threads:
            t.join()

        rotate_chunks()
        log(f"Chunks done. {mode}")


if __name__ == "__main__":
    main()
