# Widgets

All widget modules are auto-discovered from `src/widgets/w_*.py`.

## Widget Interface

Each widget module must have:

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Display name |
| `priority` | `int` | Sort order (lower = first) |
| `view_time` | `int` | Seconds to display |
| `is_active(hud, music)` | `-> bool` | Has content? |
| `draw(hud, x, y, w, h, music)` | `-> bool` | Render widget |
| `urgency(hud, music)` | `-> int` | Priority boost (optional) |

## Built-in Widgets

### w_battery

**Source:** [`src/widgets/w_battery.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_battery.py)

### w_camera

*Camera widget — live feed preview from connected cameras.*

**Source:** [`src/widgets/w_camera.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_camera.py)

### w_connectivity

*Connectivity widget -- WiFi + Bluetooth unified.*

**Source:** [`src/widgets/w_connectivity.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_connectivity.py)

### w_dashcam

*Dashcam status widget.*

**Source:** [`src/widgets/w_dashcam.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_dashcam.py)

### w_map

*Mini-Map widget — GPS position, compass heading, and movement trail from Cobra RAD 700i.*

**Source:** [`src/widgets/w_map.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_map.py)

### w_music

*Music / Now Playing widget.*

**Source:** [`src/widgets/w_music.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_music.py)

### w_radar

*Radar Detector widget — Cobra RAD 700i alerts and status.*

**Source:** [`src/widgets/w_radar.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_radar.py)

### w_recent

*Recently Played widget — shows last few tracks from Spotify.*

**Source:** [`src/widgets/w_recent.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_recent.py)

### w_system

*System Info widget -- uptime, disk usage, and version.*

**Source:** [`src/widgets/w_system.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_system.py)

### w_trip

*Trip Computer widget — full session stats for 2014 Honda Accord Hybrid.*

**Source:** [`src/widgets/w_trip.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_trip.py)

### w_weather

*Weather widget -- current conditions via wttr.in (no API key needed).*

**Source:** [`src/widgets/w_weather.py`](https://github.com/grabercn/Car-HUD/blob/main/src/widgets/w_weather.py)

