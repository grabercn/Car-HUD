"""Camera feed widget — shows live camera preview when cameras connected."""

import os
import json
import time
import subprocess
import pygame

name = "Camera"
priority = 50
view_time = 5
show_every = 90  # show once every 90 seconds unless recording starts

_cam_count = 0
_last_check = 0
_frame_cache = None
_frame_time = 0


def _check_cameras():
    """Check how many USB cameras are connected."""
    global _cam_count, _last_check
    now = time.time()
    if now - _last_check < 10:
        return _cam_count
    _last_check = now

    count = 0
    # Quick check: /dev/video0, /dev/video2, etc.
    for i in range(0, 8, 2):
        if os.path.exists(f"/dev/video{i}"):
            count += 1

    # Also check dashcam data
    try:
        with open("/tmp/car-hud-dashcam-data") as f:
            d = json.load(f)
            if time.time() - d.get("timestamp", 0) < 60:
                count = max(count, d.get("cam_count", 0))
    except Exception:
        pass

    _cam_count = count
    return count


def is_active(hud, music):
    return _check_cameras() > 0


def urgency(hud, music):
    # Only promote if dashcam just started recording
    try:
        with open("/tmp/car-hud-dashcam-data") as f:
            d = json.load(f)
            if d.get("recording") and time.time() - d.get("started", 0) < 10:
                return -30  # briefly promote
    except Exception:
        pass
    return 0


def _grab_frame():
    """Grab a single JPEG frame from the first camera."""
    global _frame_cache, _frame_time
    now = time.time()
    if _frame_cache and now - _frame_time < 2:
        return _frame_cache

    try:
        # Use ffmpeg to grab one frame
        proc = subprocess.run([
            "ffmpeg", "-f", "v4l2", "-video_size", "320x240",
            "-i", "/dev/video0", "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-"
        ], capture_output=True, timeout=3)

        if proc.returncode == 0 and len(proc.stdout) > 100:
            _frame_cache = proc.stdout
            _frame_time = now
            return _frame_cache
    except Exception:
        pass
    return None


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t
    n = _cam_count

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Camera icon
    ix, iy = x + 16, y + h // 2
    pygame.draw.rect(s, t["primary"], (ix - 7, iy - 5, 14, 10), border_radius=3)
    pygame.draw.circle(s, t["bg"], (ix, iy), 3)
    pygame.draw.polygon(s, t["primary"], [(ix + 6, iy - 3), (ix + 10, iy - 5), (ix + 10, iy + 5), (ix + 6, iy + 3)])

    # Camera count and status
    label = f"{n} Camera{'s' if n > 1 else ''}"
    lt = hud.font_md.render(label, True, t["text_bright"])
    s.blit(lt, (x + 30, y + h // 2 - 12))

    # Recording status
    try:
        with open("/tmp/car-hud-dashcam-data") as f:
            d = json.load(f)
        if d.get("recording"):
            # Blinking red dot
            if int(time.time() * 2) % 2:
                pygame.draw.circle(s, (220, 45, 45), (x + w - 20, y + h // 2 - 4), 5)
            rt = hud.font_xs.render("REC", True, (220, 45, 45))
            s.blit(rt, (x + w - 45, y + h // 2 - 6))
            size_mb = d.get("size_mb", 0)
            st = hud.font_xs.render(f"{size_mb:.0f}MB", True, t["text_dim"])
            s.blit(st, (x + 30, y + h // 2 + 6))
        else:
            st = hud.font_xs.render("Standby", True, t["text_dim"])
            s.blit(st, (x + 30, y + h // 2 + 6))
    except Exception:
        st = hud.font_xs.render("Ready", True, t["text_dim"])
        s.blit(st, (x + 30, y + h // 2 + 6))

    return True
