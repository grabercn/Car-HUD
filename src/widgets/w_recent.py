"""Recently Played widget -- shows last few tracks from Spotify.

Fetches the five most recently played tracks via the Spotify API in a
background thread.  Hidden while music is actively playing (the Music
widget handles that).
"""

import json
import os
import time
import threading
import pygame

try:
    from config import PROJECT_DIR, SPOTIFY_KEYS, SPOTIFY_TOKEN, GREEN, AMBER, RED
except ImportError:
    PROJECT_DIR = "/home/chrismslist/car-hud"
    SPOTIFY_KEYS = "/home/chrismslist/car-hud/.keys.json"
    SPOTIFY_TOKEN = "/home/chrismslist/car-hud/.spotify_token"
    GREEN = (0, 180, 85)
    AMBER = (220, 160, 0)
    RED = (220, 45, 45)

name = "Recent"
priority = 30
view_time = 10
requires_online = True

_tracks = []
_last_fetch = 0
_fetching = False


def _fetch_recent():
    """Fetch recently played tracks from Spotify API in background.

    Uses spotipy with OAuth credentials stored in PROJECT_DIR.
    """
    global _fetching
    if _fetching:
        return
    _fetching = True
    try:
        import sys
        sys.path.insert(0, PROJECT_DIR)
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        with open(SPOTIFY_KEYS) as f:
            keys = json.load(f)

        auth = SpotifyOAuth(
            client_id=keys.get("spotify_client_id", ""),
            client_secret=keys.get("spotify_client_secret", ""),
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="user-read-recently-played",
            cache_path=SPOTIFY_TOKEN,
            open_browser=False)

        sp = spotipy.Spotify(auth_manager=auth, requests_timeout=10)
        results = sp.current_user_recently_played(limit=5)

        tracks = []
        for item in results.get("items", []):
            tr = item.get("track", {})
            tracks.append({
                "name": tr.get("name", ""),
                "artist": ", ".join(a.get("name", "") for a in tr.get("artists", [])),
            })
        _tracks.clear()
        _tracks.extend(tracks)
    except Exception:
        pass
    _fetching = False


def is_active(hud, music):
    """Return True when there are recent tracks and music is NOT playing.

    The Music widget handles the active-playback case.
    """
    global _last_fetch
    try:
        if music.get("playing"):
            return False
        # Fetch every 5 minutes
        if time.time() - _last_fetch > 300:
            _last_fetch = time.time()
            threading.Thread(target=_fetch_recent, daemon=True).start()
        return len(_tracks) > 0
    except Exception:
        return False


def urgency(hud, music):
    """Low urgency informational widget."""
    return 0


def draw(hud, x, y, w, h, music):
    """Render recently played track list with history-clock icon."""
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    compact = h < 65

    # Header icon -- history clock
    hx, hy = x + 14, y + 14
    pygame.draw.circle(s, t["primary"], (hx, hy), 8, 2)
    pygame.draw.line(s, t["primary"], (hx, hy), (hx, hy - 5), 2)
    pygame.draw.line(s, t["primary"], (hx, hy), (hx + 3, hy + 1), 2)
    # Arrow
    pygame.draw.line(s, t["primary"], (hx - 8, hy), (hx - 5, hy - 3), 2)
    pygame.draw.line(s, t["primary"], (hx - 8, hy), (hx - 5, hy + 3), 2)

    header_font = hud.font_xs if compact else hud.font_sm
    ht = header_font.render("Recently Played", True, t["text_bright"])
    s.blit(ht, (x + 28, y + 6))

    # List tracks
    if not _tracks:
        return True

    max_tracks = 2 if compact else 3
    ty = y + 26
    avail_h = max(1, h - 28)
    line_h = max(14, avail_h // min(max_tracks, len(_tracks)))
    for i, tr in enumerate(_tracks[:max_tracks]):
        if ty + line_h > y + h:
            break
        tr_name = tr.get("name", "")[:20]
        tr_artist = tr.get("artist", "")[:15]
        # Track name
        nt = hud.font_xs.render(tr_name, True, t["text_med"])
        s.blit(nt, (x + 10, ty))
        # Artist -- right aligned
        at = hud.font_xs.render(tr_artist, True, t["text_dim"])
        s.blit(at, (x + w - at.get_width() - 10, ty))
        ty += line_h

    return True
