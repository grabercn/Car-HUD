"""Camera widget -- live feed preview from connected cameras.

Shows thumbnail previews grabbed via ffmpeg in background threads.
Supports one or two cameras side-by-side.  Frame capture is throttled
to every 3 seconds per camera to keep CPU usage low on the Pi 3B+.
"""

import os
import json
import time
import subprocess
import threading
import pygame

try:
    from config import DASHCAM_DATA, GREEN, AMBER, RED
except ImportError:
    DASHCAM_DATA = "/tmp/car-hud-dashcam-data"
    GREEN = (0, 180, 85)
    AMBER = (220, 160, 0)
    RED = (220, 45, 45)

name = "Camera"
priority = 50
view_time = 8
show_every = 90

_cam_count = 0
_last_check = 0
_frames = {}       # cam_idx -> pygame.Surface
_frame_times = {}   # cam_idx -> timestamp
_fetching = set()   # which cams are currently being grabbed


def _check_cameras():
    """Count connected video devices, cross-reference with dashcam service.

    Cached for 10 seconds to avoid repeated filesystem probes.
    """
    global _cam_count, _last_check
    now = time.time()
    if now - _last_check < 10:
        return _cam_count
    _last_check = now
    count = 0
    for i in range(0, 8, 2):
        if os.path.exists(f"/dev/video{i}"):
            count += 1
    try:
        with open(DASHCAM_DATA) as f:
            d = json.load(f)
            if time.time() - d.get("timestamp", 0) < 60:
                count = max(count, d.get("cam_count", 0))
    except Exception:
        pass
    _cam_count = count
    return count


def _grab_frame(cam_idx):
    """Grab a single frame from camera in background thread."""
    if cam_idx in _fetching:
        return
    _fetching.add(cam_idx)

    def _do():
        try:
            dev = f"/dev/video{cam_idx * 2}"
            proc = subprocess.run([
                "ffmpeg", "-f", "v4l2", "-video_size", "160x120",
                "-framerate", "5", "-i", dev,
                "-frames:v", "1", "-f", "rawvideo",
                "-pix_fmt", "rgb24", "-"
            ], capture_output=True, timeout=4)
            if proc.returncode == 0 and len(proc.stdout) == 160 * 120 * 3:
                surf = pygame.image.fromstring(proc.stdout, (160, 120), "RGB")
                _frames[cam_idx] = surf
                _frame_times[cam_idx] = time.time()
        except Exception:
            pass
        _fetching.discard(cam_idx)

    threading.Thread(target=_do, daemon=True).start()


def is_active(hud, music):
    """Return True when at least one camera is detected."""
    try:
        return _check_cameras() > 0
    except Exception:
        return False


def urgency(hud, music):
    """Promote briefly when dashcam recording just started."""
    try:
        with open(DASHCAM_DATA) as f:
            d = json.load(f)
            if d.get("recording") and time.time() - d.get("started", 0) < 10:
                return -30
    except Exception:
        pass
    return 0


def draw(hud, x, y, w, h, music):
    """Render camera preview thumbnails and recording status badge."""
    s = hud.surf
    t = hud.t
    n = _cam_count

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Grab fresh frames every 3 seconds
    for i in range(min(n, 2)):
        if i not in _frame_times or time.time() - _frame_times.get(i, 0) > 3:
            _grab_frame(i)

    # Recording status
    recording = False
    rec_size = 0
    try:
        with open(DASHCAM_DATA) as f:
            d = json.load(f)
            recording = d.get("recording", False)
            rec_size = d.get("size_mb", 0)
    except Exception:
        pass

    if n >= 2:
        # Two cameras -- side by side
        fw = max(1, (w - 16) // 2)
        fh = max(1, h - 8)
        for i in range(2):
            fx = x + 4 + i * (fw + 8)
            fy = y + 4
            if i in _frames:
                scaled = pygame.transform.scale(_frames[i], (fw, fh))
                s.blit(scaled, (fx, fy))
            else:
                pygame.draw.rect(s, t["border"], (fx, fy, fw, fh), border_radius=4)
                lt = hud.font_xs.render(f"Cam {i}", True, t["text_dim"])
                s.blit(lt, (fx + fw // 2 - lt.get_width() // 2, fy + fh // 2 - 6))

    elif n == 1:
        # One camera -- preview on left, status on right
        fw = max(1, min(w // 2 - 8, int(h * 1.33)))
        fh = max(1, h - 8)
        fx, fy = x + 4, y + 4
        if 0 in _frames:
            scaled = pygame.transform.scale(_frames[0], (fw, fh))
            s.blit(scaled, (fx, fy))
        else:
            pygame.draw.rect(s, t["border"], (fx, fy, fw, fh), border_radius=4)
            lt = hud.font_xs.render("Cam 0", True, t["text_dim"])
            s.blit(lt, (fx + fw // 2 - lt.get_width() // 2, fy + fh // 2 - 6))

        # Status text on right
        tx = fx + fw + 10
        cy = y + h // 2
        ct = hud.font_md.render("1 Camera", True, t["text_bright"])
        s.blit(ct, (tx, cy - 12))
        if recording:
            if int(time.time() * 2) % 2:
                pygame.draw.circle(s, RED, (tx + 4, cy + 10), 4)
            rt = hud.font_sm.render(f"REC {rec_size:.0f}MB", True, RED)
            s.blit(rt, (tx + 12, cy + 4))
        else:
            st = hud.font_sm.render("Standby", True, t["text_dim"])
            s.blit(st, (tx, cy + 4))
    else:
        lt = hud.font_sm.render("No cameras", True, t["text_dim"])
        s.blit(lt, (x + w // 2 - lt.get_width() // 2, y + h // 2 - 6))

    # REC badge in top-right corner
    if recording:
        if int(time.time() * 2) % 2:
            pygame.draw.circle(s, RED, (x + w - 14, y + 12), 5)

    return True
