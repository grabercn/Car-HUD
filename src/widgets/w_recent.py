"""Recently Played widget — shows last few tracks from Spotify."""

import json
import os
import time
import threading
import pygame

name = "Recent"
priority = 30
view_time = 10
requires_online = True

_tracks = []
_last_fetch = 0
_fetching = False


def _fetch_recent():
    """Fetch recently played from Spotify API."""
    global _fetching
    if _fetching:
        return
    _fetching = True
    try:
        import sys
        sys.path.insert(0, "/home/chrismslist/car-hud")
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        keys_file = "/home/chrismslist/car-hud/.keys.json"
        token_file = "/home/chrismslist/car-hud/.spotify_token"

        with open(keys_file) as f:
            keys = json.load(f)

        auth = SpotifyOAuth(
            client_id=keys.get("spotify_client_id", ""),
            client_secret=keys.get("spotify_client_secret", ""),
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="user-read-recently-played",
            cache_path=token_file,
            open_browser=False)

        sp = spotipy.Spotify(auth_manager=auth, requests_timeout=10)
        results = sp.current_user_recently_played(limit=5)

        tracks = []
        for item in results.get("items", []):
            t = item.get("track", {})
            tracks.append({
                "name": t.get("name", ""),
                "artist": ", ".join(a["name"] for a in t.get("artists", [])),
            })
        _tracks.clear()
        _tracks.extend(tracks)
    except Exception:
        pass
    _fetching = False


def is_active(hud, music):
    global _last_fetch
    # Don't show if music is currently playing — music widget handles that
    if music.get("playing"):
        return False
    # Fetch every 5 minutes
    if time.time() - _last_fetch > 300:
        _last_fetch = time.time()
        threading.Thread(target=_fetch_recent, daemon=True).start()
    return len(_tracks) > 0


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Header icon — history clock
    hx, hy = x + 14, y + 14
    pygame.draw.circle(s, t["primary"], (hx, hy), 8, 2)
    pygame.draw.line(s, t["primary"], (hx, hy), (hx, hy - 5), 2)
    pygame.draw.line(s, t["primary"], (hx, hy), (hx + 3, hy + 1), 2)
    # Arrow
    pygame.draw.line(s, t["primary"], (hx - 8, hy), (hx - 5, hy - 3), 2)
    pygame.draw.line(s, t["primary"], (hx - 8, hy), (hx - 5, hy + 3), 2)

    ht = hud.font_sm.render("Recently Played", True, t["text_bright"])
    s.blit(ht, (x + 28, y + 6))

    # List tracks
    ty = y + 26
    line_h = max(14, (h - 28) // min(3, len(_tracks)))
    for i, tr in enumerate(_tracks[:3]):
        if ty + line_h > y + h:
            break
        name = tr.get("name", "")[:20]
        artist = tr.get("artist", "")[:15]
        # Track name
        nt = hud.font_xs.render(name, True, t["text_med"])
        s.blit(nt, (x + 10, ty))
        # Artist — right aligned
        at = hud.font_xs.render(artist, True, t["text_dim"])
        s.blit(at, (x + w - at.get_width() - 10, ty))
        ty += line_h

    return True
