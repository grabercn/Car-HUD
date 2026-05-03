# Services

All services are systemd units in `/etc/systemd/system/`.

## Service Reference

| Service | Script | User | Restart | Purpose |
|---------|--------|------|---------|---------|
| `car-hud` | `hud.py` | chrismslist | always/2s | Main display |
| `car-hud-obd` | `obd_service.py` | chrismslist | always/5s | OBD-II + Cobra BLE |
| `car-hud-spotify` | `spotify_service.py` | chrismslist | always/5s | Music polling |
| `car-hud-web` | `web_service.py` | chrismslist | always/5s | Web server :8080 |
| `car-hud-wifi` | `wifi_service.py` | root | always/5s | WiFi management |
| `car-hud-voice` | `voice_service.py` | chrismslist | always/5s | Voice control |
| `car-hud-display` | `display_service.py` | root | always/5s | PWM brightness |
| `car-hud-touch` | `touch_service.py` | chrismslist | always/3s | Touch input |
| `car-hud-cobra` | `cobra_service.py` | chrismslist | always/10s | Radar detector |
| `car-hud-battery` | `battery_monitor.py` | chrismslist | always/10s | Battery health |
| `car-hud-dashcam` | `dashcam_service.py` | chrismslist | always/5s | Video recording |
| `car-hud-splash` | `splash_service.py` | root | no | Boot splash |
| `car-hud-updater` | `update.sh` | root | no | OTA updates |
| `bt-autoconnect` | `bt_autoconnect.sh` | root | always/5s | Phone reconnect |

## Managing Services

```bash
# Check status
systemctl is-active car-hud

# Restart a service
sudo systemctl restart car-hud

# View logs
journalctl -u car-hud --no-pager -n 50

# Enable/disable on boot
sudo systemctl enable car-hud-cobra
sudo systemctl disable car-hud-cobra
```
