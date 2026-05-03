# Data Flow

Services communicate through JSON files in `/tmp/`. Each file has a `timestamp` field.

## Signal Files

| File | Writer | Readers | Update Rate | Contents |
|------|--------|---------|-------------|----------|
| `car-hud-obd-data` | obd_service | hud, battery_monitor, widgets | ~20Hz (fast PIDs) | `connected`, `data.RPM`, `data.SPEED`, `data.ENGINE_LOAD`, etc. |
| `car-hud-music-data` | spotify_service | hud, widgets | 3s | `playing`, `track`, `artist`, `progress`, `duration`, `device` |
| `car-hud-cobra-data` | cobra_service | hud, widgets | 0.5s | `connected`, `alert`, `alert_strength`, `gps_lat`, `gps_lon` |
| `car-hud-battery-data` | battery_monitor | hud, widgets | 1s | `soc`, `pack_voltage`, `health_score`, `power_kw`, trends |
| `car-hud-wifi-data` | wifi_service | hud, widgets | 5s | `state`, `ssid`, `ip` |
| `car-hud-dashcam-data` | dashcam_service | hud, widgets | 5s | `recording`, `cam_count`, `size_mb` |
| `car-hud-display-data` | display_service | web_service | 1s | `brightness`, `lux`, `auto_mode` |
| `car-hud-gps` | cobra_service | weather widget | 0.5s | `lat`, `lon`, `speed`, `heading` |
| `car-hud-voice-signal` | voice_service | hud | on command | `action`, `target`, `raw`, `time` |
| `car-hud-touch` | touch_service | hud | on gesture | `gesture`, `x`, `y`, `time` |
| `car-hud-mic-level` | voice_service | hud | 0.1s | Text: `level1 level2` |

## Persistent Files

| File | Purpose |
|------|---------|
| `.theme` | Current theme + auto mode |
| `.brightness` | Display brightness 0-100 |
| `.widget-config.json` | Enabled/disabled widgets |
| `.pinned-widgets.json` | Pinned widget names |
| `.obd_adapter` | Saved OBD BLE MAC address |
| `.cobra_adapter` | Saved Cobra BLE MAC address |
| `.paired_phone` | Saved phone MAC + name |
| `.spotify_token` | Spotify OAuth cache |
| `.keys.json` | API keys (Spotify, Gemini) |
| `battery_history.db` | SQLite — SOC, voltage, power over time |

## Data Staleness

Each reader checks `time.time() - data["timestamp"]` against a threshold. If data is too old, it's treated as disconnected/unavailable. Thresholds:

- OBD: 10 seconds
- Music: 30 seconds
- Cobra: 30 seconds
- Battery: 10 seconds
- WiFi: 30 seconds
