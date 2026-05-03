# src/widgets/

Widget modules auto-discovered by the HUD at runtime.
Each file (`w_*.py`) exports `name`, `priority`, `draw()`, and `is_active()`.

[Back to main README](../../README.md) | [Back to src/](../README.md)

> Auto-generated on 2026-05-03 by
> [`../../.github/scripts/generate_readmes.py`](../../.github/scripts/generate_readmes.py)

---

## Stats

- **Total widgets:** 11
- **Require internet:** 2
- **Average priority:** 27

---

## Widget Reference

| File | Name | Description | Priority | View Time | Show Every | Online? | Size | Modified |
|------|------|-------------|----------|-----------|------------|---------|------|----------|
| [`w_battery.py`](w_battery.py) | HV Battery | Honda Accord Hybrid HV Battery Widget | 3 | 15s | 0s | No | 31.1 KB | 2026-05-03 |
| [`w_radar.py`](w_radar.py) | Radar | Radar Detector widget -- Cobra RAD 700i alerts and status | 5 | 15s | 0s | No | 4.4 KB | 2026-05-03 |
| [`w_music.py`](w_music.py) | Music | Music / Now Playing widget | 10 | 12s | 0s | No | 5.1 KB | 2026-05-03 |
| [`w_trip.py`](w_trip.py) | Trip | Trip Computer widget — full session stats for 2014 Honda Accord Hybrid | 10 | 12s | 0s | No | 11.4 KB | 2026-05-03 |
| [`w_connectivity.py`](w_connectivity.py) | Connectivity | Connectivity widget -- WiFi + Bluetooth unified | 15 | 5s | 60s | No | 4.9 KB | 2026-05-03 |
| [`w_dashcam.py`](w_dashcam.py) | Dashcam | Dashcam status widget | 15 | 6s | 0s | No | 2.4 KB | 2026-05-03 |
| [`w_weather.py`](w_weather.py) | Weather | Weather widget -- current conditions via wttr.in (no API key needed) | 25 | 6s | 180s | Yes | 6.2 KB | 2026-05-03 |
| [`w_recent.py`](w_recent.py) | Recent | Recently Played widget -- shows last few tracks from Spotify | 30 | 10s | 0s | Yes | 4.1 KB | 2026-05-03 |
| [`w_map.py`](w_map.py) | Map | Mini-Map widget -- GPS position, compass heading, and movement trail | 40 | 8s | 0s | No | 9.2 KB | 2026-05-03 |
| [`w_camera.py`](w_camera.py) | Camera | Camera widget -- live feed preview from connected cameras | 50 | 8s | 90s | No | 5.4 KB | 2026-05-03 |
| [`w_system.py`](w_system.py) | System | System Info widget -- uptime, disk usage, and version | 99 | 4s | 120s | No | 2.2 KB | 2026-05-03 |

---

## How Widgets Work

1. The HUD scans `src/widgets/w_*.py` on startup.
2. Each widget declares a `priority` (lower = shown first).
3. `is_active(hud, music)` determines if the widget has content right now.
4. Active widgets are sorted by effective priority and drawn into the
   scrolling carousel on the current page.
5. `show_every` adds a cooldown (seconds) so low-value widgets don't dominate.
6. `requires_online = True` hides the widget when there is no internet.
