"""Trip Computer widget — full session stats for 2014 Honda Accord Hybrid.

Tracks: duration, distance, average/max speed, EV vs gas ratio, fuel economy.
Reads OBD data from hud.smooth_data (populated from /tmp/car-hud-obd-data).
RPM=0 indicates EV mode on the hybrid drivetrain.
"""

import json
import time
import math
import pygame

name = "Trip"
priority = 10          # high — useful driving data
view_time = 12

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

# ── Session state ──
_trip_start = 0.0           # epoch when OBD first connected
_total_distance_mi = 0.0    # accumulated miles
_max_speed_mph = 0.0        # peak speed
_speed_sum = 0.0            # running sum for average
_speed_count = 0            # sample count
_ev_samples = 0             # samples where RPM == 0
_gas_samples = 0            # samples where RPM > 0
_last_sample_time = 0.0     # for distance integration
_fuel_start = -1.0          # fuel level at trip start (%)
_fuel_readings = 0          # how many fuel readings we have


def _reset():
    """Reset all accumulators."""
    global _trip_start, _total_distance_mi, _max_speed_mph
    global _speed_sum, _speed_count, _ev_samples, _gas_samples
    global _last_sample_time, _fuel_start, _fuel_readings
    _trip_start = 0.0
    _total_distance_mi = 0.0
    _max_speed_mph = 0.0
    _speed_sum = 0.0
    _speed_count = 0
    _ev_samples = 0
    _gas_samples = 0
    _last_sample_time = 0.0
    _fuel_start = -1.0
    _fuel_readings = 0


def is_active(hud, music):
    global _trip_start
    try:
        with open("/tmp/car-hud-obd-data") as f:
            d = json.load(f)
        connected = d.get("connected", False)
        fresh = time.time() - d.get("timestamp", 0) < 10
        if connected and fresh:
            if _trip_start == 0:
                _trip_start = time.time()
            return True
    except Exception:
        pass
    # OBD gone for a while — reset if it was a long gap
    if _trip_start > 0 and time.time() - _last_sample_time > 120:
        _reset()
    return _trip_start > 0 and _total_distance_mi > 0.05


def urgency(hud, music):
    # Slightly promote when there is meaningful trip data
    if _total_distance_mi > 0.5:
        return -5
    return 0


def _update(hud):
    """Sample OBD data and accumulate trip statistics."""
    global _total_distance_mi, _max_speed_mph, _speed_sum, _speed_count
    global _ev_samples, _gas_samples, _last_sample_time
    global _fuel_start, _fuel_readings

    now = time.time()
    speed_kmh = hud.smooth_data.get("SPEED", 0)
    speed_mph = speed_kmh * 0.621371
    rpm = hud.smooth_data.get("RPM", 0)
    fuel = hud.smooth_data.get("FUEL_LEVEL", -1)

    # Distance integration (trapezoidal: use current speed * dt)
    if _last_sample_time > 0:
        dt_hours = (now - _last_sample_time) / 3600.0
        if dt_hours < 0.01 and speed_mph > 0.5:   # ignore huge gaps
            _total_distance_mi += speed_mph * dt_hours
    _last_sample_time = now

    # Speed stats — ignore < 2 mph (stopped/creeping)
    if speed_mph > 2:
        _speed_sum += speed_mph
        _speed_count += 1
        if speed_mph > _max_speed_mph:
            _max_speed_mph = speed_mph

    # EV / Gas tracking
    if speed_mph > 2:
        if rpm < 100:
            _ev_samples += 1
        else:
            _gas_samples += 1

    # Fuel level at start
    if fuel > 0 and _fuel_start < 0 and _fuel_readings < 3:
        _fuel_readings += 1
        if _fuel_readings >= 3:
            _fuel_start = fuel

    return speed_mph, rpm, fuel


def _fmt_duration(seconds):
    """Format seconds into compact h:mm:ss or m:ss string."""
    if seconds < 0:
        return "0:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _fmt_duration_long(seconds):
    """Format duration as '1h 23m' for compact view."""
    if seconds < 0:
        return "0m"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


# ── Drawing ──

def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    speed_mph, rpm, fuel_level = _update(hud)

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    compact = h < 65
    if compact:
        _draw_compact(hud, s, t, x, y, w, h, speed_mph, rpm, fuel_level)
    else:
        _draw_full(hud, s, t, x, y, w, h, speed_mph, rpm, fuel_level)

    return True


def _draw_compact(hud, s, t, x, y, w, h, speed_mph, rpm, fuel_level):
    """Single-row compact strip for small widget slots."""
    cy = y + h // 2
    elapsed = time.time() - _trip_start if _trip_start > 0 else 0
    avg = _speed_sum / _speed_count if _speed_count > 0 else 0
    ev_total = _ev_samples + _gas_samples
    ev_pct = (_ev_samples / ev_total * 100) if ev_total > 0 else 0

    # Road icon — two converging lines
    ix = x + 12
    pygame.draw.line(s, t["text_med"], (ix - 4, cy + 7), (ix, cy - 7), 2)
    pygame.draw.line(s, t["text_med"], (ix + 4, cy + 7), (ix, cy - 7), 2)
    pygame.draw.line(s, t["text_dim"], (ix, cy - 1), (ix, cy + 1), 1)
    pygame.draw.line(s, t["text_dim"], (ix, cy + 4), (ix, cy + 6), 1)

    # Duration — left
    dur_t = hud.font_md.render(_fmt_duration_long(elapsed), True, t["text_bright"])
    s.blit(dur_t, (x + 24, cy - dur_t.get_height() // 2))

    # Distance — center-left
    dist_str = f"{_total_distance_mi:.1f} mi"
    dist_t = hud.font_sm.render(dist_str, True, t["text_med"])
    cx1 = x + w * 3 // 10
    s.blit(dist_t, (cx1, cy - dist_t.get_height() // 2))

    # Avg speed — center
    avg_str = f"avg {avg:.0f}"
    avg_t = hud.font_sm.render(avg_str, True, t["text_dim"])
    cx2 = x + w // 2
    s.blit(avg_t, (cx2, cy - avg_t.get_height() // 2))

    # EV ratio — right
    if ev_total > 10:
        ev_color = GREEN if ev_pct > 50 else AMBER if ev_pct > 20 else t["text_dim"]
        ev_str = f"EV {ev_pct:.0f}%"
        ev_t = hud.font_sm.render(ev_str, True, ev_color)
        s.blit(ev_t, (x + w - ev_t.get_width() - 10, cy - ev_t.get_height() // 2))


def _draw_full(hud, s, t, x, y, w, h, speed_mph, rpm, fuel_level):
    """Full multi-row trip computer layout."""
    elapsed = time.time() - _trip_start if _trip_start > 0 else 0
    avg = _speed_sum / _speed_count if _speed_count > 0 else 0
    ev_total = _ev_samples + _gas_samples
    ev_pct = (_ev_samples / ev_total * 100) if ev_total > 0 else 0

    pad = 6
    inner_x = x + pad
    inner_w = w - pad * 2

    # ── Top row: Current speed (prominent) + trip timer ──
    top_y = y + pad

    # Speed — large, left-of-center
    spd_str = f"{speed_mph:.0f}"
    spd_t = hud.font_xxl.render(spd_str, True, t["text_bright"])
    spd_x = inner_x + 4
    s.blit(spd_t, (spd_x, top_y))

    # "mph" label under the speed number
    mph_t = hud.font_xs.render("mph", True, t["text_dim"])
    s.blit(mph_t, (spd_x + spd_t.get_width() + 3, top_y + spd_t.get_height() - mph_t.get_height()))

    # EV indicator next to speed
    ev_mode = rpm < 100 and speed_mph > 1
    if ev_mode:
        ev_label = hud.font_sm.render("EV", True, GREEN)
        ev_lx = spd_x + spd_t.get_width() + 3
        s.blit(ev_label, (ev_lx, top_y + 2))

    # Trip duration — top right
    dur_str = _fmt_duration(elapsed)
    dur_t = hud.font_lg.render(dur_str, True, t["text_bright"])
    dur_x = x + w - dur_t.get_width() - pad - 2
    s.blit(dur_t, (dur_x, top_y))
    dur_lbl = hud.font_xs.render("trip", True, t["text_dim"])
    s.blit(dur_lbl, (dur_x, top_y + dur_t.get_height()))

    # ── Divider line ──
    div_y = top_y + max(spd_t.get_height(), dur_t.get_height()) + dur_lbl.get_height() + 3
    pygame.draw.line(s, t["border"], (inner_x, div_y), (inner_x + inner_w, div_y), 1)

    # ── Stats grid below divider ──
    row_y = div_y + 4
    remaining_h = (y + h - pad) - row_y

    # Calculate column layout: 3 columns
    col_w = inner_w // 3

    # Row 1: Distance | Avg Speed | Max Speed
    _draw_stat(hud, s, t, inner_x, row_y, col_w,
               f"{_total_distance_mi:.1f}", "mi", t["text_bright"])
    _draw_stat(hud, s, t, inner_x + col_w, row_y, col_w,
               f"{avg:.0f}", "avg mph", t["text_med"])
    max_color = RED if _max_speed_mph > 80 else AMBER if _max_speed_mph > 65 else t["text_med"]
    _draw_stat(hud, s, t, inner_x + col_w * 2, row_y, col_w,
               f"{_max_speed_mph:.0f}", "max mph", max_color)

    # Row 2 (if space): EV Ratio | Fuel Economy | Fuel Used
    row2_y = row_y + 28
    if row2_y + 24 <= y + h - pad:
        # EV / Gas ratio bar
        _draw_ev_bar(hud, s, t, inner_x, row2_y, col_w - 4, ev_pct, ev_total)

        # Fuel economy estimate (distance / fuel used)
        fuel_now = hud.smooth_data.get("FUEL_LEVEL", -1)
        if _fuel_start > 0 and fuel_now > 0 and _fuel_start > fuel_now and _total_distance_mi > 0.5:
            # Tank is roughly 12.8 gal on 2014 Accord Hybrid
            tank_gal = 12.8
            fuel_used_gal = ((_fuel_start - fuel_now) / 100.0) * tank_gal
            if fuel_used_gal > 0.01:
                mpg = _total_distance_mi / fuel_used_gal
                mpg_color = GREEN if mpg > 45 else AMBER if mpg > 30 else RED
                _draw_stat(hud, s, t, inner_x + col_w, row2_y, col_w,
                           f"{mpg:.0f}", "mpg", mpg_color)
            else:
                _draw_stat(hud, s, t, inner_x + col_w, row2_y, col_w,
                           "--", "mpg", t["text_dim"])
        else:
            _draw_stat(hud, s, t, inner_x + col_w, row2_y, col_w,
                       "--", "mpg", t["text_dim"])

        # Fuel used percentage
        if _fuel_start > 0 and fuel_now > 0:
            used_pct = max(0, _fuel_start - fuel_now)
            _draw_stat(hud, s, t, inner_x + col_w * 2, row2_y, col_w,
                       f"-{used_pct:.1f}", "% fuel", t["text_med"])
        else:
            _draw_stat(hud, s, t, inner_x + col_w * 2, row2_y, col_w,
                       "--", "fuel", t["text_dim"])

    return True


def _draw_stat(hud, s, t, sx, sy, sw, value_str, label_str, color):
    """Draw a stat: large value on top, small label below, centered in column."""
    val_t = hud.font_md.render(value_str, True, color)
    lbl_t = hud.font_xs.render(label_str, True, t["text_dim"])
    cx = sx + sw // 2
    s.blit(val_t, (cx - val_t.get_width() // 2, sy))
    s.blit(lbl_t, (cx - lbl_t.get_width() // 2, sy + val_t.get_height()))


def _draw_ev_bar(hud, s, t, bx, by, bw, ev_pct, ev_total):
    """Draw a compact EV/Gas ratio bar with percentage."""
    bar_h = 8
    label_h = hud.font_xs.render("X", True, t["text_dim"]).get_height()

    # Label
    if ev_total > 10:
        ev_str = f"EV {ev_pct:.0f}%"
        ev_color = GREEN if ev_pct > 50 else AMBER if ev_pct > 20 else t["text_dim"]
    else:
        ev_str = "EV --"
        ev_color = t["text_dim"]
    lbl = hud.font_xs.render(ev_str, True, ev_color)
    cx = bx + bw // 2
    s.blit(lbl, (cx - lbl.get_width() // 2, by))

    # Bar background
    bar_y = by + label_h + 2
    pygame.draw.rect(s, t["border"], (bx + 4, bar_y, bw - 8, bar_h), border_radius=3)

    # EV fill (green from left), Gas fill (red/amber from right)
    if ev_total > 10:
        ev_w = max(1, int((bw - 8) * ev_pct / 100))
        pygame.draw.rect(s, GREEN, (bx + 4, bar_y, ev_w, bar_h), border_radius=3)
        gas_w = (bw - 8) - ev_w
        if gas_w > 1:
            pygame.draw.rect(s, (100, 60, 60), (bx + 4 + ev_w, bar_y, gas_w, bar_h), border_radius=3)
