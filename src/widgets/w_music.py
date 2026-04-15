"""Music / Now Playing widget."""

import os
import time
import pygame

name = "Music"
priority = 10

_last_track = ""
_track_change_time = 0


def is_active(hud, music):
    return music.get("playing", False)


def urgency(hud, music):
    """Promote to top when track changes (for 15 seconds)."""
    global _last_track, _track_change_time
    track = music.get("track", "")
    if track and track != _last_track:
        _last_track = track
        _track_change_time = time.time()
    if time.time() - _track_change_time < 15:
        return -100  # jump to top
    return -10  # still high priority when playing


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t
    track = music.get("track", "")
    artist = music.get("artist", "")

    # Album art - maximized
    art_size = min(h, w // 3)  # Use up to 1/3 of width or full height
    art_loaded = False
    try:
        art_file = "/home/chrismslist/car-hud/current_art.jpg"
        if os.path.exists(art_file) and os.path.getsize(art_file) > 100:
            from PIL import Image as PILImage
            pil = PILImage.open(art_file).convert("RGB")
            pil = pil.resize((art_size, art_size), PILImage.LANCZOS)
            art_surf = pygame.image.fromstring(pil.tobytes(), (art_size, art_size), "RGB")
            # Subtle rounded border effect using a mask
            mask = pygame.Surface((art_size, art_size), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, art_size, art_size), border_radius=8)
            art_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            
            s.blit(art_surf, (x, y + (h - art_size) // 2))
            art_loaded = True
    except Exception:
        pass

    if not art_loaded:
        pygame.draw.rect(s, t["border"], (x, y + (h - art_size) // 2, art_size, art_size), border_radius=8)
        ncx, ncy = x + art_size // 2, y + h // 2
        pygame.draw.ellipse(s, t["primary"], (ncx - 12, ncy + 4, 16, 12))
        pygame.draw.line(s, t["primary"], (ncx + 2, ncy + 10), (ncx + 2, ncy - 20), 3)
        pygame.draw.line(s, t["primary"], (ncx + 2, ncy - 20), (ncx + 12, ncy - 14), 3)

    # Info area
    tx = x + art_size + 16
    tw = w - art_size - 16
    
    # Vertically center the text info based on available height
    info_h = 70
    ty = y + (h - info_h) // 2

    # Track title (Large)
    has_cjk = any(ord(c) > 0x2E80 for c in track)
    track_font = hud.font_cjk if has_cjk and hud.font_cjk else hud.font_lg
    tt = track_font.render(track, True, t["text_bright"])
    # Truncate if too long
    if tt.get_width() > tw:
        for i in range(len(track), 0, -1):
            tt = track_font.render(track[:i] + "...", True, t["text_bright"])
            if tt.get_width() <= tw: break
    s.blit(tt, (tx, ty))

    # Artist name (Medium)
    has_cjk_a = any(ord(c) > 0x2E80 for c in artist)
    artist_font = hud.font_cjk_sm if has_cjk_a and hasattr(hud, "font_cjk_sm") and hud.font_cjk_sm else hud.font_md
    at = artist_font.render(artist, True, t["text_med"])
    if at.get_width() > tw:
        for i in range(len(artist), 0, -1):
            at = artist_font.render(artist[:i] + "...", True, t["text_med"])
            if at.get_width() <= tw: break
    s.blit(at, (tx, ty + 36))

    # Progress Bar
    prog = max(0, music.get("progress", 0))
    dur = max(0, music.get("duration", 0))
    if prog == 0 and dur > 0 and music.get("timestamp"):
        prog = min(time.time() - music["timestamp"], dur)

    pbar_y = ty + 68
    if dur > 0:
        pygame.draw.rect(s, t["border"], (tx, pbar_y, tw, 6), border_radius=3)
        fw = int(tw * min(prog / dur, 1))
        if fw > 0:
            pygame.draw.rect(s, t["primary"], (tx, pbar_y, fw, 6), border_radius=3)

        prog_m, prog_s = int(prog) // 60, int(prog) % 60
        dur_m, dur_s = int(dur) // 60, int(dur) % 60
        time_t = hud.font_sm.render(f"{prog_m}:{prog_s:02d} / {dur_m}:{dur_s:02d}", True, t["text_dim"])
        s.blit(time_t, (tx, pbar_y + 12))

    dev_name = music.get("device", "")
    if dev_name:
        dt = hud.font_sm.render(dev_name, True, t["primary_dim"])
        s.blit(dt, (tx + tw - dt.get_width(), pbar_y + 12 if dur > 0 else pbar_y))

    return True
