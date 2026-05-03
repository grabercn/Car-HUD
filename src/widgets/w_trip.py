"""Trip Computer widget — comprehensive session stats for 2014 Honda Accord Hybrid.

Tracks: duration, distance, average/max speed, EV vs gas ratio, fuel economy,
fuel level delta, cost estimate, and HV battery efficiency.

Data sources:
  hud.smooth_data  — smoothed OBD values (SPEED, RPM, FUEL_LEVEL, etc.)
  /tmp/car-hud-obd-data — raw OBD JSON for fuel reads with caching

RPM = 0 indicates EV mode on the hybrid drivetrain.
FUEL_LEVEL = 0-100% of the 15.8 gallon tank.
"""

import json
import os
import time
import pygame

name = "Trip"
priority = 10
view_time = 12

# ── Constants ──
TANK_SIZE_GAL = 15.8          # 2014 Honda Accord Hybrid fuel tank
KMH_TO_MPH = 0.621371
DEFAULT_GAS_PRICE = 3.50      # $/gal configurable
OBD_FILE = "/tmp/car-hud-obd-data"
FUEL_SETTLE_SAMPLES = 5       # readings before locking start fuel
OBD_DISCONNECT_RESET_S = 120  # reset trip after 2 min disconnect
FUEL_CACHE_INTERVAL_S = 5     # re-read OBD file at most every 5s

# ── Colors ──
GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)
EV_GREEN = (30, 200, 100)
GAS_BLUE = (50, 130, 220)
WHITE = (255, 255, 255)

# ── Session state ──
_trip_start = 0.0
_total_distance_mi = 0.0
_max_speed_mph = 0.0
_speed_sum = 0.0              # sum of moving speeds for avg
_speed_samples = 0            # count of moving speed samples
_ev_samples = 0               # samples in EV (RPM < 100, moving)
_gas_samples = 0              # samples in gas (RPM >= 100, moving)
_ev_distance_mi = 0.0         # miles driven in EV mode
_gas_distance_mi = 0.0        # miles driven in gas mode
_last_sample_time = 0.0
_last_obd_valid_time = 0.0    # last time OBD data was fresh

# Fuel tracking
_fuel_start_pct = -1.0        # fuel % at trip start (locked after settle)
_fuel_settle_count = 0        # readings collected before locking
_fuel_settle_sum = 0.0        # running sum for averaging
_fuel_now_pct = -1.0          # latest fuel % reading

# HV battery tracking
_hv_start_pct = -1.0          # HV SOC at trip start
_hv_now_pct = -1.0            # latest HV SOC

# OBD file cache
_obd_cache = {}
_obd_cache_time = 0.0

# Config
_gas_price = DEFAULT_GAS_PRICE


def _reset():
    """Reset all trip accumulators."""
    global _trip_start, _total_distance_mi, _max_speed_mph
    global _speed_sum, _speed_samples, _ev_samples, _gas_samples
    global _ev_distance_mi, _gas_distance_mi
    global _last_sample_time, _last_obd_valid_time
    global _fuel_start_pct, _fuel_settle_count, _fuel_settle_sum, _fuel_now_pct
    global _hv_start_pct, _hv_now_pct
    _trip_start = 0.0
    _total_distance_mi = 0.0
    _max_speed_mph = 0.0
    _speed_sum = 0.0
    _speed_samples = 0
    _ev_samples = 0
    _gas_samples = 0
    _ev_distance_mi = 0.0
    _gas_distance_mi = 0.0
    _last_sample_time = 0.0
    _last_obd_valid_time = 0.0
    _fuel_start_pct = -1.0
    _fuel_settle_count = 0
    _fuel_settle_sum = 0.0
    _fuel_now_pct = -1.0
    _hv_start_pct = -1.0
    _hv_now_pct = -1.0


def _read_obd_file():
    """Read /tmp/car-hud-obd-data with caching to avoid per-frame I/O."""
    global _obd_cache, _obd_cache_time
    now = time.time()
    if now - _obd_cache_time < FUEL_CACHE_INTERVAL_S:
        return _obd_cache
    try:
        mt = os.path.getmtime(OBD_FILE)
        if mt != _obd_cache.get("_mt"):
            with open(OBD_FILE) as f:
                _obd_cache = json.load(f)
            _obd_cache["_mt"] = mt
        _obd_cache_time = now
    except Exception:
        pass
    return _obd_cache


def is_active(hud, music):
    global _trip_start, _last_obd_valid_time
    obd = _read_obd_file()
    connected = obd.get("connected", False)
    fresh = time.time() - obd.get("timestamp", 0) < 10

    if connected and fresh:
        _last_obd_valid_time = time.time()
        if _trip_start == 0:
            _trip_start = time.time()
        return True

    # OBD gone — reset after disconnect timeout
    if _trip_start > 0 and _last_obd_valid_time > 0:
        if time.time() - _last_obd_valid_time > OBD_DISCONNECT_RESET_S:
            _reset()
            return False

    # Still show trip if we have meaningful data
    return _trip_start > 0 and _total_distance_mi > 0.05


def urgency(hud, music):
    if _total_distance_mi > 1.0:
        return -5
    if _total_distance_mi > 0.5:
        return -2
    return 0


def _update(hud):
    """Sample OBD data and accumulate all trip statistics."""
    global _total_distance_mi, _max_speed_mph, _speed_sum, _speed_samples
    global _ev_samples, _gas_samples, _ev_distance_mi, _gas_distance_mi
    global _last_sample_time
    global _fuel_start_pct, _fuel_settle_count, _fuel_settle_sum, _fuel_now_pct
    global _hv_start_pct, _hv_now_pct

    now = time.time()

    # Read from smooth_data (populated by hud main loop)
    speed_kmh = hud.smooth_data.get("SPEED", 0)
    speed_mph = speed_kmh * KMH_TO_MPH
    rpm = hud.smooth_data.get("RPM", 0)

    # Fuel level from smooth_data (slowly smoothed)
    fuel = hud.smooth_data.get("FUEL_LEVEL", -1)

    # HV battery SOC
    hv_soc = hud.smooth_data.get("HYBRID_BATTERY_REMAINING", -1)

    # Engine load and throttle for context
    engine_load = hud.smooth_data.get("ENGINE_LOAD", 0)
    throttle = hud.smooth_data.get("THROTTLE_POS", 0)

    # ── Distance integration ──
    if _last_sample_time > 0:
        dt_hours = (now - _last_sample_time) / 3600.0
        if 0 < dt_hours < 0.01 and speed_mph > 0.5:
            segment = speed_mph * dt_hours
            _total_distance_mi += segment
            # Track EV vs gas distance
            if rpm < 100:
                _ev_distance_mi += segment
            else:
                _gas_distance_mi += segment
    _last_sample_time = now

    # ── Speed stats (ignore stopped / creeping < 2 mph) ──
    if speed_mph > 2:
        _speed_sum += speed_mph
        _speed_samples += 1
        if speed_mph > _max_speed_mph:
            _max_speed_mph = speed_mph

    # ── EV / Gas sample tracking (only while moving) ──
    if speed_mph > 2:
        if rpm < 100:
            _ev_samples += 1
        else:
            _gas_samples += 1

    # ── Fuel level at trip start (average first N readings to settle) ──
    if fuel > 0:
        _fuel_now_pct = fuel
        if _fuel_start_pct < 0:
            _fuel_settle_count += 1
            _fuel_settle_sum += fuel
            if _fuel_settle_count >= FUEL_SETTLE_SAMPLES:
                _fuel_start_pct = _fuel_settle_sum / _fuel_settle_count

    # ── HV battery start ──
    if hv_soc > 0:
        _hv_now_pct = hv_soc
        if _hv_start_pct < 0:
            _hv_start_pct = hv_soc

    return speed_mph, rpm, fuel, hv_soc, engine_load, throttle


# ── Computed metrics ──

def _gallons_used():
    """Calculate gallons of fuel consumed this trip."""
    if _fuel_start_pct > 0 and _fuel_now_pct > 0 and _fuel_start_pct > _fuel_now_pct:
        return (_fuel_start_pct - _fuel_now_pct) / 100.0 * TANK_SIZE_GAL
    return 0.0


def _fuel_cost():
    """Estimated fuel cost for this trip."""
    return _gallons_used() * _gas_price


def _mpg():
    """Miles per gallon (gas only). Returns 0 if insufficient data."""
    gal = _gallons_used()
    if gal > 0.01 and _total_distance_mi > 0.1:
        return _total_distance_mi / gal
    return 0.0


def _ev_pct():
    """Percentage of trip driven in EV mode."""
    total = _ev_samples + _gas_samples
    if total > 0:
        return _ev_samples / total * 100
    return 0.0


def _avg_speed():
    """Average moving speed in mph."""
    if _speed_samples > 0:
        return _speed_sum / _speed_samples
    return 0.0


def _elapsed():
    """Trip duration in seconds."""
    if _trip_start > 0:
        return time.time() - _trip_start
    return 0.0


# ── Formatting helpers ──

def _fmt_duration(seconds):
    """h:mm:ss or m:ss."""
    if seconds < 0:
        return "0:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _fmt_duration_short(seconds):
    """Compact: 1h 23m."""
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

    speed_mph, rpm, fuel, hv_soc, engine_load, throttle = _update(hud)

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    compact = h < 65
    if compact:
        _draw_compact(hud, s, t, x, y, w, h, speed_mph, rpm)
    else:
        _draw_full(hud, s, t, x, y, w, h, speed_mph, rpm, fuel, hv_soc)

    return True


# ── Compact: single-row strip ──

def _draw_compact(hud, s, t, x, y, w, h, speed_mph, rpm):
    """duration | distance | fuel used | EV% -- one row."""
    cy = y + h // 2
    elapsed = _elapsed()
    ev = _ev_pct()
    gal = _gallons_used()
    total_samp = _ev_samples + _gas_samples

    pad = 10
    col_w = (w - pad * 2) // 4
    cx = x + pad

    # Road icon
    ix = cx + 4
    pygame.draw.line(s, t["text_med"], (ix - 4, cy + 7), (ix, cy - 7), 2)
    pygame.draw.line(s, t["text_med"], (ix + 4, cy + 7), (ix, cy - 7), 2)
    cx += 14

    # Duration
    dur_t = hud.font_md.render(_fmt_duration_short(elapsed), True, t["text_bright"])
    s.blit(dur_t, (cx, cy - dur_t.get_height() // 2))
    cx += col_w

    # Distance
    dist_str = f"{_total_distance_mi:.1f} mi"
    dist_t = hud.font_sm.render(dist_str, True, t["text_med"])
    s.blit(dist_t, (cx, cy - dist_t.get_height() // 2))
    cx += col_w

    # Fuel used
    if gal > 0.01:
        fuel_str = f"-{gal:.2f}g"
        fuel_t = hud.font_sm.render(fuel_str, True, AMBER)
    else:
        fuel_str = "--g"
        fuel_t = hud.font_sm.render(fuel_str, True, t["text_dim"])
    s.blit(fuel_t, (cx, cy - fuel_t.get_height() // 2))
    cx += col_w

    # EV%
    if total_samp > 10:
        ev_color = EV_GREEN if ev > 50 else AMBER if ev > 20 else t["text_dim"]
        ev_str = f"EV {ev:.0f}%"
        ev_t = hud.font_sm.render(ev_str, True, ev_color)
        s.blit(ev_t, (x + w - ev_t.get_width() - 10, cy - ev_t.get_height() // 2))


# ── Full: two-row layout with visuals ──

def _draw_full(hud, s, t, x, y, w, h, speed_mph, rpm, fuel, hv_soc):
    """Row 1: speed + EV/GAS indicator + trip time
    Row 2: distance | fuel stats | MPG | EV/Gas split bar"""
    elapsed = _elapsed()
    avg = _avg_speed()
    ev = _ev_pct()
    gal = _gallons_used()
    mpg = _mpg()
    cost = _fuel_cost()
    total_samp = _ev_samples + _gas_samples

    pad = 6
    inner_x = x + pad
    inner_w = w - pad * 2

    # ═════════════════════════════════════════════
    # ROW 1: Current speed | EV/GAS mode | Trip time
    # ═════════════════════════════════════════════
    top_y = y + pad

    # Speed -- large, left side
    spd_str = f"{speed_mph:.0f}"
    spd_t = hud.font_xxl.render(spd_str, True, t["text_bright"])
    spd_x = inner_x + 4
    s.blit(spd_t, (spd_x, top_y))

    # "mph" label
    mph_lbl = hud.font_xs.render("mph", True, t["text_dim"])
    s.blit(mph_lbl, (spd_x + spd_t.get_width() + 3,
                     top_y + spd_t.get_height() - mph_lbl.get_height()))

    # EV / GAS indicator next to speed
    ev_mode = rpm < 100 and speed_mph > 1
    mode_x = spd_x + spd_t.get_width() + 3
    if ev_mode:
        mode_lbl = hud.font_sm.render("EV", True, EV_GREEN)
        s.blit(mode_lbl, (mode_x, top_y + 2))
        # Small lightning bolt
        bx = mode_x + mode_lbl.get_width() + 3
        by = top_y + 4
        pygame.draw.lines(s, EV_GREEN, False, [
            (bx + 4, by), (bx + 1, by + 6), (bx + 5, by + 6),
            (bx + 2, by + 12)
        ], 2)
    elif speed_mph > 2:
        mode_lbl = hud.font_sm.render("GAS", True, GAS_BLUE)
        s.blit(mode_lbl, (mode_x, top_y + 2))

    # Trip duration -- top right
    dur_str = _fmt_duration(elapsed)
    dur_t = hud.font_lg.render(dur_str, True, t["text_bright"])
    dur_x = x + w - dur_t.get_width() - pad - 2
    s.blit(dur_t, (dur_x, top_y))
    dur_lbl = hud.font_xs.render("trip", True, t["text_dim"])
    s.blit(dur_lbl, (dur_x, top_y + dur_t.get_height()))

    # ── Divider line ──
    div_y = top_y + max(spd_t.get_height(), dur_t.get_height()) + dur_lbl.get_height() + 3
    pygame.draw.line(s, t["border"], (inner_x, div_y), (inner_x + inner_w, div_y), 1)

    # ═════════════════════════════════════════════
    # ROW 2: Stats grid below divider
    # ═════════════════════════════════════════════
    row_y = div_y + 4
    remaining_h = (y + h - pad) - row_y

    # Decide layout: 4 columns if wide enough, else 3
    num_cols = 4 if inner_w > 300 else 3
    col_w = inner_w // num_cols

    # ── Sub-row A: Distance | Fuel used | MPG | Avg/Max speed ──
    _draw_stat(hud, s, t, inner_x, row_y, col_w,
               f"{_total_distance_mi:.1f}", "miles", t["text_bright"])

    # Fuel used: show gallons + % delta
    if gal > 0.01:
        fuel_str = f"{gal:.2f}"
        fuel_lbl = f"gal (${cost:.2f})"
        _draw_stat(hud, s, t, inner_x + col_w, row_y, col_w,
                   fuel_str, fuel_lbl, AMBER)
    elif _fuel_start_pct > 0 and _fuel_now_pct > 0:
        delta = _fuel_start_pct - _fuel_now_pct
        _draw_stat(hud, s, t, inner_x + col_w, row_y, col_w,
                   f"{delta:+.1f}%", "fuel", t["text_med"])
    else:
        _draw_stat(hud, s, t, inner_x + col_w, row_y, col_w,
                   "--", "fuel", t["text_dim"])

    # MPG
    if mpg > 0:
        mpg_color = GREEN if mpg > 45 else AMBER if mpg > 30 else RED
        _draw_stat(hud, s, t, inner_x + col_w * 2, row_y, col_w,
                   f"{mpg:.0f}", "mpg", mpg_color)
    else:
        _draw_stat(hud, s, t, inner_x + col_w * 2, row_y, col_w,
                   "--", "mpg", t["text_dim"])

    # 4th column: avg + max speed (stacked)
    if num_cols >= 4:
        _draw_speed_col(hud, s, t, inner_x + col_w * 3, row_y, col_w, avg)

    # ── Sub-row B: EV/Gas split bar + fuel level + extra stats ──
    row_b_y = row_y + 30
    if row_b_y + 24 <= y + h - pad:
        # EV/Gas split bar (takes 2 columns width)
        bar_w = col_w * 2 - 8
        _draw_ev_gas_bar(hud, s, t, inner_x, row_b_y, bar_w, total_samp, ev)

        # Fuel level: start -> now
        fuel_col_x = inner_x + col_w * 2
        if _fuel_start_pct > 0 and _fuel_now_pct > 0:
            _draw_fuel_delta(hud, s, t, fuel_col_x, row_b_y, col_w)
        elif _fuel_now_pct > 0:
            _draw_stat(hud, s, t, fuel_col_x, row_b_y, col_w,
                       f"{_fuel_now_pct:.0f}%", "fuel lvl", t["text_med"])
        else:
            _draw_stat(hud, s, t, fuel_col_x, row_b_y, col_w,
                       "--", "fuel lvl", t["text_dim"])

        # 4th column: EV/Gas mile split
        if num_cols >= 4:
            mile_col_x = inner_x + col_w * 3
            _draw_ev_miles(hud, s, t, mile_col_x, row_b_y, col_w)

    # ── Sub-row C (if tall enough): HV battery + efficiency ──
    row_c_y = row_b_y + 28
    if row_c_y + 20 <= y + h - pad:
        _draw_efficiency_row(hud, s, t, inner_x, row_c_y, inner_w,
                             num_cols, col_w, avg)


# ── Drawing helpers ──

def _draw_stat(hud, s, t, sx, sy, sw, value_str, label_str, color):
    """Stat: large value on top, small label below, centered in column."""
    val_t = hud.font_md.render(value_str, True, color)
    lbl_t = hud.font_xs.render(label_str, True, t["text_dim"])
    cx = sx + sw // 2
    s.blit(val_t, (cx - val_t.get_width() // 2, sy))
    s.blit(lbl_t, (cx - lbl_t.get_width() // 2, sy + val_t.get_height()))


def _draw_speed_col(hud, s, t, sx, sy, sw, avg):
    """Draw avg and max speed stacked in one column."""
    cx = sx + sw // 2
    # Avg
    avg_t = hud.font_sm.render(f"avg {avg:.0f}", True, t["text_med"])
    s.blit(avg_t, (cx - avg_t.get_width() // 2, sy))
    # Max
    max_color = RED if _max_speed_mph > 80 else AMBER if _max_speed_mph > 65 else t["text_med"]
    max_t = hud.font_sm.render(f"max {_max_speed_mph:.0f}", True, max_color)
    s.blit(max_t, (cx - max_t.get_width() // 2, sy + avg_t.get_height() + 1))


def _draw_fuel_delta(hud, s, t, fx, fy, fw):
    """Draw fuel start -> now as a compact visual."""
    cx = fx + fw // 2
    # Arrow showing fuel delta: "47 > 43"
    start_str = f"{_fuel_start_pct:.0f}"
    now_str = f"{_fuel_now_pct:.0f}%"
    arrow_t = hud.font_sm.render(f"{start_str}>{now_str}", True, t["text_med"])
    s.blit(arrow_t, (cx - arrow_t.get_width() // 2, fy))
    lbl = hud.font_xs.render("fuel %", True, t["text_dim"])
    s.blit(lbl, (cx - lbl.get_width() // 2, fy + arrow_t.get_height()))


def _draw_ev_miles(hud, s, t, mx, my, mw):
    """Show EV miles / gas miles split."""
    cx = mx + mw // 2
    ev_str = f"{_ev_distance_mi:.1f}"
    gas_str = f"{_gas_distance_mi:.1f}"
    # EV miles in green
    ev_t = hud.font_sm.render(ev_str, True, EV_GREEN)
    # Separator
    sep_t = hud.font_sm.render("/", True, t["text_dim"])
    # Gas miles in blue
    gas_t = hud.font_sm.render(gas_str, True, GAS_BLUE)

    total_w = ev_t.get_width() + sep_t.get_width() + gas_t.get_width()
    sx = cx - total_w // 2
    s.blit(ev_t, (sx, my))
    sx += ev_t.get_width()
    s.blit(sep_t, (sx, my))
    sx += sep_t.get_width()
    s.blit(gas_t, (sx, my))

    lbl = hud.font_xs.render("ev/gas mi", True, t["text_dim"])
    s.blit(lbl, (cx - lbl.get_width() // 2, my + ev_t.get_height()))


def _draw_ev_gas_bar(hud, s, t, bx, by, bw, total_samp, ev_pct):
    """EV/Gas split bar: green (EV) | blue (gas) with percentages."""
    bar_h = 10
    label_h = hud.font_xs.render("X", True, t["text_dim"]).get_height()

    # Labels above bar
    if total_samp > 10:
        ev_str = f"EV {ev_pct:.0f}%"
        gas_str = f"GAS {100 - ev_pct:.0f}%"
        ev_color = EV_GREEN
        gas_color = GAS_BLUE
    else:
        ev_str = "EV --"
        gas_str = "GAS --"
        ev_color = t["text_dim"]
        gas_color = t["text_dim"]

    ev_lbl = hud.font_xs.render(ev_str, True, ev_color)
    gas_lbl = hud.font_xs.render(gas_str, True, gas_color)
    s.blit(ev_lbl, (bx, by))
    s.blit(gas_lbl, (bx + bw - gas_lbl.get_width(), by))

    # Bar background
    bar_y = by + label_h + 2
    pygame.draw.rect(s, t["border"], (bx, bar_y, bw, bar_h), border_radius=4)

    if total_samp > 10:
        # EV fill from left (green)
        ev_w = max(1, int(bw * ev_pct / 100))
        pygame.draw.rect(s, EV_GREEN, (bx, bar_y, ev_w, bar_h), border_radius=4)
        # Gas fill from right (blue)
        gas_w = bw - ev_w
        if gas_w > 1:
            pygame.draw.rect(s, GAS_BLUE, (bx + ev_w, bar_y, gas_w, bar_h),
                             border_radius=4)
        # Thin separator line at the boundary
        if 0 < ev_w < bw:
            pygame.draw.line(s, t["bg"], (bx + ev_w, bar_y),
                             (bx + ev_w, bar_y + bar_h - 1), 1)


def _draw_efficiency_row(hud, s, t, rx, ry, rw, num_cols, col_w, avg):
    """Bottom row: HV battery delta, efficiency metrics, max speed."""
    # HV battery delta
    if _hv_start_pct > 0 and _hv_now_pct > 0:
        hv_delta = _hv_now_pct - _hv_start_pct
        hv_color = GREEN if hv_delta > 0 else AMBER if hv_delta > -5 else RED
        hv_str = f"{hv_delta:+.1f}%"
        _draw_stat(hud, s, t, rx, ry, col_w,
                   hv_str, "HV batt", hv_color)
    else:
        _draw_stat(hud, s, t, rx, ry, col_w,
                   "--", "HV batt", t["text_dim"])

    # Avg speed (if not shown in row A)
    if num_cols < 4:
        _draw_stat(hud, s, t, rx + col_w, ry, col_w,
                   f"{avg:.0f}", "avg mph", t["text_med"])
        max_color = RED if _max_speed_mph > 80 else AMBER if _max_speed_mph > 65 else t["text_med"]
        _draw_stat(hud, s, t, rx + col_w * 2, ry, col_w,
                   f"{_max_speed_mph:.0f}", "max mph", max_color)
    else:
        # Miles per kWh estimate (using HV battery SOC change and distance)
        if (_hv_start_pct > 0 and _hv_now_pct > 0 and
                _hv_start_pct > _hv_now_pct and _ev_distance_mi > 0.1):
            # Rough: Accord Hybrid pack ~1.3 kWh usable
            kwh_used = (_hv_start_pct - _hv_now_pct) / 100.0 * 1.3
            if kwh_used > 0.01:
                mi_per_kwh = _ev_distance_mi / kwh_used
                eff_color = GREEN if mi_per_kwh > 3 else AMBER if mi_per_kwh > 1.5 else RED
                _draw_stat(hud, s, t, rx + col_w, ry, col_w,
                           f"{mi_per_kwh:.1f}", "mi/kWh", eff_color)
            else:
                _draw_stat(hud, s, t, rx + col_w, ry, col_w,
                           "--", "mi/kWh", t["text_dim"])
        else:
            _draw_stat(hud, s, t, rx + col_w, ry, col_w,
                       "--", "mi/kWh", t["text_dim"])

        # 12V system voltage
        v12 = hud.smooth_data.get("CONTROL_MODULE_VOLTAGE", 0)
        if v12 > 0:
            v12_color = GREEN if v12 > 12.4 else AMBER if v12 > 11.8 else RED
            _draw_stat(hud, s, t, rx + col_w * 2, ry, col_w,
                       f"{v12:.1f}V", "12V sys", v12_color)
        else:
            _draw_stat(hud, s, t, rx + col_w * 2, ry, col_w,
                       "--", "12V sys", t["text_dim"])

        # Max speed in 4th column
        max_color = RED if _max_speed_mph > 80 else AMBER if _max_speed_mph > 65 else t["text_med"]
        _draw_stat(hud, s, t, rx + col_w * 3, ry, col_w,
                   f"{_max_speed_mph:.0f}", "max mph", max_color)
