# REST API

Base URL: `http://Car-HUD.local:8080`

## GET Endpoints

| Endpoint | Response | Description |
|----------|----------|-------------|
| `/status` | JSON | All system status (OBD, WiFi, music, dashcam, etc.) |
| `/api/theme` | JSON | Current theme name and auto mode |
| `/api/widgets` | JSON | All widgets with enabled/priority state |
| `/api/brightness` | JSON | Current brightness level and lux |
| `/api/battery` | JSON | HV battery data (SOC, voltage, health) |
| `/api/battery/history` | JSON | Last 24h of battery readings |
| `/api/wifi/scan` | JSON | Available WiFi networks |
| `/api/bt/scan` | JSON | Nearby Bluetooth devices (8s scan) |
| `/api/terminal/read` | JSON | Terminal output buffer |
| `/screenshot` | BMP | Current HUD screenshot |
| `/stream` | MJPEG | Live HUD video stream |

## POST Endpoints

| Endpoint | Parameters | Description |
|----------|-----------|-------------|
| `/api/theme/set` | `theme=blue&auto=false` | Set theme |
| `/api/widget/set` | `name=Music&enabled=true` | Enable/disable widget |
| `/api/widget/pin` | `name=Battery&pinned=true` | Pin/unpin widget |
| `/api/brightness/set` | `level=80` | Set brightness 0-100 |
| `/api/wifi/connect` | `ssid=Name&password=pass` | Connect to WiFi |
| `/api/bt/pair` | `mac=AA:BB:CC:DD:EE:FF` | Pair Bluetooth device |
| `/api/bt/audio` | `enable=true` | Toggle Spotify Connect |
| `/api/terminal/write` | `cmd=ls -la` | Send command to terminal |

## Pages

| URL | Description |
|-----|-------------|
| `/` | Live HUD view (MJPEG stream) |
| `/camera` | Live camera feeds |
| `/dashcam` | Saved recordings browser |
| `/settings` | System settings (WiFi, BT, theme, widgets, brightness) |
| `/terminal` | Web-based bash terminal |
