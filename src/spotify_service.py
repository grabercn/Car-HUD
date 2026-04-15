#!/usr/bin/env python3
"""Car-HUD Spotify Service
Polls Spotify API for now-playing data. Works regardless of where audio plays.
Also supports playback control via voice commands.

First run: opens auth URL — visit it in browser, paste redirect URL back.
After that: token auto-refreshes forever.

Writes to /tmp/car-hud-music-data for HUD display.
Reads /tmp/car-hud-voice-signal for playback commands.
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE = os.path.join(INSTALL_DIR, ".keys.json")
TOKEN_FILE = os.path.join(INSTALL_DIR, ".spotify_token")
MUSIC_FILE = "/tmp/car-hud-music-data"
VOICE_FILE = "/tmp/car-hud-voice-signal"
LOG_FILE = "/tmp/car-hud-spotify.log"

SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
ART_PATH = "/home/chrismslist/car-hud/current_art.jpg"
ART_CACHE_DIR = os.path.join(INSTALL_DIR, "art_cache")

import threading
import urllib.request
import hashlib
_last_art_url = [""]  # mutable for closure access

os.makedirs(ART_CACHE_DIR, exist_ok=True)


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 30000:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()[-50:]
            with open(LOG_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def write_music(data):
    data["timestamp"] = time.time()
    data["source"] = "spotify"
    try:
        with open(MUSIC_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_keys():
    try:
        with open(KEYS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_spotify():
    """Get authenticated Spotify client."""
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    keys = load_keys()
    client_id = keys.get("spotify_client_id", "")
    client_secret = keys.get("spotify_client_secret", "")

    if not client_id or not client_secret:
        log("No Spotify credentials in .keys.json")
        return None

    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_path=TOKEN_FILE,
        open_browser=False
    )

    # Check for cached token
    token_info = auth.get_cached_token()

    if not token_info:
        # Need user authorization
        auth_url = auth.get_authorize_url()
        log(f"=== SPOTIFY AUTH NEEDED ===")
        log(f"Visit this URL in your browser:")
        log(f"{auth_url}")
        log(f"After authorizing, paste the redirect URL here.")
        log(f"Or visit http://Car-HUD.local:8080/spotify/auth to see the URL")

        # Write auth URL for web interface
        write_music({"playing": False, "auth_needed": True, "auth_url": auth_url})

        # Wait for token file to appear (user completes auth via web)
        while not os.path.exists(TOKEN_FILE):
            time.sleep(5)
            # Check if auth was completed via web endpoint
            if os.path.exists(TOKEN_FILE):
                break

        token_info = auth.get_cached_token()

    sp = spotipy.Spotify(auth_manager=auth, requests_timeout=10)
    log("Spotify authenticated!")
    return sp


def check_voice_commands(sp):
    """Check for Spotify playback control commands."""
    try:
        with open(VOICE_FILE) as f:
            data = json.load(f)
        if time.time() - data.get("time", 0) > 5:
            return
        action = data.get("action", "")
        target = data.get("target", "")
        raw = data.get("raw", "").lower()

        if action != "music" and "spotify" not in raw and "music" not in raw:
            return

        try:
            if "pause" in raw or "stop" in raw:
                sp.pause_playback()
                log("Paused")
            elif "play" in raw or "resume" in raw:
                sp.start_playback()
                log("Playing")
            elif "next" in raw or "skip" in raw:
                sp.next_track()
                log("Next track")
            elif "previous" in raw or "back" in raw:
                sp.previous_track()
                log("Previous track")
            elif "volume up" in raw or "louder" in raw:
                current = sp.current_playback()
                if current:
                    vol = min(100, current.get("device", {}).get("volume_percent", 50) + 15)
                    sp.volume(vol)
                    log(f"Volume: {vol}%")
            elif "volume down" in raw or "quieter" in raw:
                current = sp.current_playback()
                if current:
                    vol = max(0, current.get("device", {}).get("volume_percent", 50) - 15)
                    sp.volume(vol)
                    log(f"Volume: {vol}%")
        except Exception as e:
            log(f"Playback control error: {e}")
    except Exception:
        pass


def main():
    log("Spotify service starting...")

    keys = load_keys()
    if not keys.get("spotify_client_id"):
        log("No Spotify credentials — sleeping")
        write_music({"playing": False, "status": "No Spotify credentials"})
        time.sleep(300)
        return

    sp = get_spotify()
    if not sp:
        time.sleep(60)
        return

    # Get auth manager reference for token refresh
    auth = sp.auth_manager

    write_music({"playing": False, "status": "Connected to Spotify"})
    log("Polling now-playing...")

    last_voice_check = 0

    while True:
        try:
            current = sp.current_playback()

            if current and current.get("is_playing"):
                item = current.get("item", {})
                track = item.get("name", "Unknown")
                artists = ", ".join(a["name"] for a in item.get("artists", []))
                album = item.get("album", {}).get("name", "")
                duration = max(0, (item.get("duration_ms") or 0)) / 1000
                progress = max(0, (current.get("progress_ms") or 0)) / 1000
                device = current.get("device", {}).get("name", "")
                volume = current.get("device", {}).get("volume_percent", 0)
                shuffle = current.get("shuffle_state", False)
                repeat = current.get("repeat_state", "off")

                # Album art URL (for future use)
                images = item.get("album", {}).get("images", [])
                art_url = images[0]["url"] if images else ""

                write_music({
                    "playing": True,
                    "track": track,
                    "artist": artists,
                    "album": album,
                    "duration": duration,
                    "progress": progress,
                    "device": device,
                    "volume": volume,
                    "shuffle": shuffle,
                    "repeat": repeat,
                    "art_url": art_url,
                })

                # Download album art — check cache first
                if art_url and art_url != _last_art_url[0]:
                    _last_art_url[0] = art_url
                    def _dl(url):
                        try:
                            cache_key = hashlib.md5(url.encode()).hexdigest()[:12]
                            cache_path = os.path.join(ART_CACHE_DIR, f"{cache_key}.jpg")
                            if os.path.exists(cache_path):
                                # Cache hit — just copy
                                import shutil
                                shutil.copy2(cache_path, ART_PATH)
                            else:
                                # Download and cache permanently
                                urllib.request.urlretrieve(url, ART_PATH)
                                import shutil
                                shutil.copy2(ART_PATH, cache_path)
                        except Exception:
                            pass
                    threading.Thread(target=_dl, args=(art_url,), daemon=True).start()
            else:
                write_music({
                    "playing": False,
                    "status": "Paused" if current else "Not playing"
                })

        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "token" in err_str.lower():
                # Token expired — force refresh
                try:
                    token = auth.get_cached_token()
                    if token and token.get("refresh_token"):
                        auth.refresh_access_token(token["refresh_token"])
                        log("Token refreshed")
                except Exception:
                    log(f"Refresh failed: {e}")
            elif "timeout" in err_str.lower() or "resolve" in err_str.lower():
                # Network issue — just wait
                time.sleep(5)
            else:
                log(f"Poll error: {e}")
                write_music({"playing": False, "status": "Reconnecting..."})

        # Check voice commands
        now = time.time()
        if now - last_voice_check > 1:
            last_voice_check = now
            check_voice_commands(sp)

        time.sleep(3)  # Poll every 3 seconds


if __name__ == "__main__":
    main()
