"""Dashcam status widget.

Shows a blinking red recording indicator with camera count and storage
used.  Promoted to high urgency for 10 seconds when recording first starts.
"""

import json
import time
import pygame

try:
    from config import DASHCAM_DATA, GREEN, AMBER, RED
except ImportError:
    DASHCAM_DATA = "/tmp/car-hud-dashcam-data"
    GREEN = (0, 180, 85)
    AMBER = (220, 160, 0)
    RED = (220, 45, 45)

name = "Dashcam"
priority = 15
view_time = 6  # seconds

_was_recording = False
_rec_start_time = 0


def is_active(hud, music):
    """Return True when the dashcam service is actively recording."""
    try:
        with open(DASHCAM_DATA) as f:
            cd = json.load(f)
        return bool(time.time() - cd.get("timestamp", 0) < 60 and cd.get("recording"))
    except Exception:
        return False


def urgency(hud, music):
    """Promote when recording just started (10 seconds)."""
    global _was_recording, _rec_start_time
    try:
        recording = is_active(hud, music)
    except Exception:
        recording = False
    if recording and not _was_recording:
        _rec_start_time = time.time()
    _was_recording = recording
    if recording and time.time() - _rec_start_time < 10:
        return -50
    return 0


def draw(hud, x, y, w, h, music):
    """Render blinking REC dot, camera count, and storage used."""
    s = hud.surf
    t = hud.t

    try:
        with open(DASHCAM_DATA) as f:
            cd = json.load(f)
    except Exception:
        cd = {}

    recording = cd.get("recording", False)
    cam_count = cd.get("cam_count", 0)
    size_mb = cd.get("size_mb", 0)

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)
    pygame.draw.rect(s, t["border_lite"], (x, y, w, h), 1, border_radius=6)

    compact = h < 65
    cy = y + h // 2

    # Blinking red dot when recording
    if recording and int(time.time() * 2) % 2 == 0:
        pygame.draw.circle(s, RED, (x + 24, cy), 8)
    else:
        pygame.draw.circle(s, RED, (x + 24, cy), 8, 2)

    label = f"REC {cam_count} cam" + ("s" if cam_count > 1 else "")
    label_font = hud.font_sm if compact else hud.font_md
    rt = label_font.render(label, True, t["text_bright"])

    # Vertically center text block
    ty = y + (h - rt.get_height() - 20) // 2
    s.blit(rt, (x + 48, ty))

    size_font = hud.font_xs if compact else hud.font_sm
    st = size_font.render(f"{size_mb:.0f} MB", True, t["text_dim"])
    s.blit(st, (x + 48, ty + rt.get_height() + 4))

    return True
