"""Dashcam status widget."""

import json
import time
import pygame

name = "Dashcam"
priority = 15

RED = (220, 45, 45)
_was_recording = False
_rec_start_time = 0


def is_active(hud, music):
    try:
        with open("/tmp/car-hud-dashcam-data") as f:
            cd = json.load(f)
        return time.time() - cd.get("timestamp", 0) < 60 and cd.get("recording")
    except Exception:
        return False


def urgency(hud, music):
    """Promote when recording just started (10 seconds)."""
    global _was_recording, _rec_start_time
    recording = is_active(hud, music)
    if recording and not _was_recording:
        _rec_start_time = time.time()
    _was_recording = recording
    if recording and time.time() - _rec_start_time < 10:
        return -50
    return 0


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    try:
        with open("/tmp/car-hud-dashcam-data") as f:
            cd = json.load(f)
    except Exception:
        return False

    recording = cd.get("recording", False)
    cam_count = cd.get("cam_count", 0)
    size_mb = cd.get("size_mb", 0)

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=8)
    pygame.draw.rect(s, t["border_lite"], (x, y, w, h), 1, border_radius=8)

    cy = y + h // 2

    # Blinking red dot when recording
    if recording and int(time.time() * 2) % 2 == 0:
        pygame.draw.circle(s, RED, (x + 24, cy), 8)
    else:
        pygame.draw.circle(s, RED, (x + 24, cy), 8, 2)

    label = f"REC {cam_count} cam" + ("s" if cam_count > 1 else "")
    rt = hud.font_md.render(label, True, t["text_bright"])
    
    # Vertically center text block
    ty = y + (h - rt.get_height() - 20) // 2
    s.blit(rt, (x + 48, ty))

    st = hud.font_sm.render(f"{size_mb:.0f} MB", True, t["text_dim"])
    s.blit(st, (x + 48, ty + rt.get_height() + 4))

    return True
