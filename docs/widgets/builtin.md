# Built-in Widgets

## Music (`w_music.py`)
Now playing information from Spotify. Album art, track/artist, progress bar, device name. Promotes to top for 15 seconds when track changes.

**Priority:** 10 | **View time:** 12s | **Urgency:** -100 on track change

## HV Battery (`w_battery.py`)
Honda Accord Hybrid high-voltage battery monitor. Shows SOC%, pack voltage, power flow, health score, and mini trend graph. 12-module battery visualization in full mode.

**Priority:** 3 | **View time:** 15s | **Shows when:** OBD connected

## Radar (`w_radar.py`)
Cobra RAD 700i alert display. Red pulsing background with band name and strength bar during alerts. GPS speed when idle.

**Priority:** 5 | **View time:** 15s | **Urgency:** -200 during alert (overrides everything)

## Connectivity (`w_connectivity.py`)
WiFi + Bluetooth status side-by-side. Shows SSID, IP, connected phone name. Promotes for 10 seconds on new phone connection.

**Priority:** 15 | **View time:** 5s | **Cooldown:** 60s

## Weather (`w_weather.py`)
Current conditions via [wttr.in](https://wttr.in). Uses Cobra GPS for location when available, falls back to IP geolocation. Weather icons for sun/cloud/rain/snow.

**Priority:** 25 | **View time:** 6s | **Cooldown:** 180s | **Requires:** internet

## Camera (`w_camera.py`)
Dashcam live preview with 160x120 frame capture. Shows recording status with blinking REC indicator.

**Priority:** 50 | **View time:** 5s | **Cooldown:** 90s

## System (`w_system.py`)
Uptime and disk usage bar. Low priority fallback widget.

**Priority:** 99 | **View time:** 4s | **Cooldown:** 120s

## Trip (`w_trip.py`)
Session duration, distance, and average speed from OBD data.

**Priority:** 35 | **View time:** 7s | **Shows when:** OBD speed > 0

## Dashcam Status (`w_dashcam.py`)
Recording indicator with blinking red dot and storage size. Promotes when recording starts.

**Priority:** 15 | **View time:** 6s

## Recently Played (`w_recent.py`)
Last 3 Spotify tracks. Only shows when music is NOT playing.

**Priority:** 30 | **View time:** 10s | **Requires:** internet
