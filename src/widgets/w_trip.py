"""Trip Info widget — session duration, distance, avg speed from OBD data."""

import time
import pygame

name = "Trip"
priority = 35
view_time = 7

_trip_start = 0
_total_distance = 0.0  # miles
_speed_samples = []
_last_speed = 0
_last_sample_time = 0


def is_active(hud, music):
    global _trip_start
    # Active when OBD has speed data (car is on)
    speed = hud.smooth_data.get("SPEED", 0)
    if speed > 0 and _trip_start == 0:
        _trip_start = time.time()
    return _trip_start > 0


def urgency(hud, music):
    return 0


def draw(hud, x, y, w, h, music):
    global _total_distance, _last_speed, _last_sample_time

    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    speed_kmh = hud.smooth_data.get("SPEED", 0)
    speed_mph = speed_kmh * 0.621371
    now = time.time()

    # Accumulate distance
    if _last_sample_time > 0 and speed_mph > 0:
        dt_hours = (now - _last_sample_time) / 3600
        _total_distance += speed_mph * dt_hours
    _last_sample_time = now

    # Track speed for average
    if speed_mph > 2:
        _speed_samples.append(speed_mph)
        if len(_speed_samples) > 1000:
            _speed_samples.pop(0)

    avg_speed = sum(_speed_samples) / len(_speed_samples) if _speed_samples else 0

    # Trip duration
    if _trip_start > 0:
        elapsed = now - _trip_start
        trip_h = int(elapsed // 3600)
        trip_m = int((elapsed % 3600) // 60)
        trip_str = f"{trip_h}h {trip_m}m" if trip_h > 0 else f"{trip_m}m"
    else:
        trip_str = "0m"

    cy = y + h // 2

    # Road icon
    rx = x + 14
    pygame.draw.line(s, t["text_med"], (rx - 4, cy + 8), (rx, cy - 8), 2)
    pygame.draw.line(s, t["text_med"], (rx + 4, cy + 8), (rx, cy - 8), 2)
    pygame.draw.line(s, t["text_dim"], (rx, cy - 2), (rx, cy + 2), 1)
    pygame.draw.line(s, t["text_dim"], (rx, cy + 5), (rx, cy + 7), 1)

    # Trip time — left
    tt = hud.font_md.render(trip_str, True, t["text_bright"])
    s.blit(tt, (x + 28, cy - 12))

    # Distance — center
    dist_str = f"{_total_distance:.1f} mi"
    dt = hud.font_sm.render(dist_str, True, t["text_med"])
    s.blit(dt, (x + w // 2 - dt.get_width() // 2, cy - 8))

    # Avg speed — right
    avg_str = f"avg {avg_speed:.0f}"
    at = hud.font_sm.render(avg_str, True, t["text_dim"])
    s.blit(at, (x + w - at.get_width() - 10, cy - 8))

    return True
