# First Boot

## What Happens on Boot

1. **Splash screen** — Honda logo with animated progress bar (~20s)
2. **NTP time sync** — Sets clock via internet
3. **OBD scan** — Searches for BLE OBD adapter + Cobra radar
4. **WiFi connect** — Auto-connects to saved networks
5. **BT connect** — Reconnects to last paired phone
6. **HUD starts** — System page with rotating widgets

## Initial Configuration

### WiFi
Open `http://Car-HUD.local:8080/settings` on your phone and use the WiFi section to scan and connect.

### Bluetooth Phone
Put your phone in pairing mode, then scan from the settings page. The Pi saves the phone MAC for auto-reconnect.

### Spotify
Set up Spotify credentials in `~/.car-hud/.keys.json`:
```json
{
  "spotify_client_id": "your_id",
  "spotify_client_secret": "your_secret"
}
```
Then authenticate via `python3 ~/car-hud/spotify_service.py` (follow the OAuth URL).

### Theme
Change via settings page, voice ("Hey Honda, change to red theme"), or touch (tap status bar).

### Display Brightness
Adjust via settings page slider or voice ("Hey Honda, brightness up/down/max").
