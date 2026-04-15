"""Music / Now Playing widget."""

import os
import time
import pygame

name = "Music"
priority = 10
view_time = 12  # seconds — user needs time to read track info

_last_track = ""
_track_change_time = 0


def is_active(hud, music):
    return music.get("playing", False)


def urgency(hud, music):
    global _last_track, _track_change_time
    track = music.get("track", "")
    if track and track != _last_track:
        _last_track = track
        _track_change_time = time.time()
    if time.time() - _track_change_time < 15:
        return -100
    return -10


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t
    track = music.get("track", "")
    artist = music.get("artist", "")

    # Album art — square, vertically centered
    art_size = min(h - 4, w // 4)
    art_y = y + (h - art_size) // 2
    art_loaded = False
    try:
        art_file = "/home/chrismslist/car-hud/current_art.jpg"
        if os.path.exists(art_file) and os.path.getsize(art_file) > 100:
            from PIL import Image as PILImage
            pil = PILImage.open(art_file).convert("RGB")
            pil = pil.resize((art_size, art_size), PILImage.LANCZOS)
            art_surf = pygame.image.fromstring(pil.tobytes(), (art_size, art_size), "RGB")
            s.blit(art_surf, (x, art_y))
            art_loaded = True
    except Exception:
        pass

    if not art_loaded:
        pygame.draw.rect(s, t["border"], (x, art_y, art_size, art_size), border_radius=4)
        ncx, ncy = x + art_size // 2, art_y + art_size // 2
        pygame.draw.ellipse(s, t["primary"], (ncx - 8, ncy + 2, 12, 8))
        pygame.draw.line(s, t["primary"], (ncx + 2, ncy + 5), (ncx + 2, ncy - 12), 2)
        pygame.draw.line(s, t["primary"], (ncx + 2, ncy - 12), (ncx + 8, ncy - 8), 2)

    # Text area
    tx = x + art_size + 8
    tw = w - art_size - 12

    # Adaptive layout based on height
    compact = h < 65

    # Track title
    has_cjk = any(ord(c) > 0x2E80 for c in track)
    track_font = hud.font_cjk if has_cjk and hud.font_cjk else (hud.font_md if compact else hud.font_lg)
    tt = track_font.render(track, True, t["text_bright"])
    if tt.get_width() > tw:
        for i in range(len(track), 0, -1):
            tt = track_font.render(track[:i] + "..", True, t["text_bright"])
            if tt.get_width() <= tw:
                break
    s.blit(tt, (tx, y + 2))

    # Artist
    has_cjk_a = any(ord(c) > 0x2E80 for c in artist)
    artist_font = hud.font_cjk_sm if has_cjk_a and hasattr(hud, "font_cjk_sm") and hud.font_cjk_sm else hud.font_sm
    at = artist_font.render(artist, True, t["text_med"])
    if at.get_width() > tw:
        for i in range(len(artist), 0, -1):
            at = artist_font.render(artist[:i] + "..", True, t["text_med"])
            if at.get_width() <= tw:
                break
    artist_y = y + (20 if compact else 28)
    s.blit(at, (tx, artist_y))

    # Progress bar + time
    prog = max(0, music.get("progress", 0))
    dur = max(0, music.get("duration", 0))
    if prog == 0 and dur > 0 and music.get("timestamp"):
        prog = min(time.time() - music["timestamp"], dur)

    pbar_y = artist_y + artist_font.get_height() + 4
    if dur > 0 and pbar_y + 6 < y + h:
        pygame.draw.rect(s, t["border"], (tx, pbar_y, tw, 4), border_radius=2)
        fw = int(tw * min(prog / dur, 1))
        if fw > 0:
            pygame.draw.rect(s, t["primary"], (tx, pbar_y, fw, 4), border_radius=2)

        # Time left-aligned, device right-aligned
        prog_m, prog_s = int(prog) // 60, int(prog) % 60
        dur_m, dur_s = int(dur) // 60, int(dur) % 60
        time_str = f"{prog_m}:{prog_s:02d}/{dur_m}:{dur_s:02d}"
        time_t = hud.font_xs.render(time_str, True, t["text_dim"])
        s.blit(time_t, (tx, pbar_y + 6))

        dev_name = music.get("device", "")
        if dev_name:
            dt = hud.font_xs.render(dev_name, True, t["primary_dim"])
            s.blit(dt, (tx + tw - dt.get_width(), pbar_y + 6))

    return True
