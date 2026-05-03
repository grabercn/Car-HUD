# services/

Systemd unit files that run Car-HUD components as background services on the Pi.

[Back to main README](../README.md)

> Auto-generated on 2026-05-03 by
> [`../.github/scripts/generate_readmes.py`](../.github/scripts/generate_readmes.py)

---

## Unit Files

| File | Description | Size | Modified |
|------|-------------|------|----------|
| [`car-hud-battery.service`](car-hud-battery.service) | Car-HUD Honda Hybrid Battery Monitor | 290 B | 2026-05-02 |
| [`car-hud-cobra.service`](car-hud-cobra.service) | Car-HUD Cobra RAD 700i Radar Detector | 305 B | 2026-04-16 |
| [`car-hud-dashcam.service`](car-hud-dashcam.service) | Honda Accord Dashcam | 317 B | 2026-04-13 |
| [`car-hud-display.service`](car-hud-display.service) | Car-HUD Display Brightness Controller | 255 B | 2026-04-16 |
| [`car-hud-music.service`](car-hud-music.service) | Car-HUD Bluetooth Music Service | 298 B | 2026-04-13 |
| [`car-hud-obd.service`](car-hud-obd.service) | Honda Accord OBD-II Monitor | 363 B | 2026-04-13 |
| [`car-hud-splash.service`](car-hud-splash.service) | Honda Accord Boot Splash | 550 B | 2026-04-13 |
| [`car-hud-touch.service`](car-hud-touch.service) | Car-HUD Touch Input Service | 262 B | 2026-04-15 |
| [`car-hud-updater.service`](car-hud-updater.service) | Car-HUD Auto Updater | 305 B | 2026-04-13 |
| [`car-hud-voice.service`](car-hud-voice.service) | Honda Accord Voice Commands | 374 B | 2026-04-13 |
| [`car-hud-web.service`](car-hud-web.service) | Car-HUD Screenshot Server | 294 B | 2026-04-13 |
| [`car-hud-wifi.service`](car-hud-wifi.service) | Honda Accord WiFi Manager | 365 B | 2026-04-13 |
| [`car-hud.service`](car-hud.service) | Honda Accord HUD | 743 B | 2026-04-15 |
| [`hide-cursor.service`](hide-cursor.service) | Hide mouse cursor | 252 B | 2026-04-12 |

---

## Common Commands

```bash
# Check status of all Car-HUD services
systemctl list-units 'car-hud*'

# View logs for a specific service
journalctl -u car-hud-obd.service -f

# Restart a service
sudo systemctl restart car-hud.service

# Enable/disable a service
sudo systemctl enable car-hud-dashcam.service
sudo systemctl disable car-hud-dashcam.service
```
