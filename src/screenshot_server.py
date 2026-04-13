#!/usr/bin/env python3
"""Lightweight screenshot HTTP server.
Only runs when SSH/network is active. Serves HUD screenshots.
Access from any browser/phone: http://Car-HUD.local:8080
"""

import os
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
SCREENSHOT_PATH = "/tmp/car-hud-screenshot.bmp"
INTERVAL = 1  # seconds between screenshots


def take_screenshot():
    """Ask HUD to save a screenshot by writing a signal file."""
    try:
        with open("/tmp/car-hud-screenshot-request", "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>Car-HUD</title>
<meta name="viewport" content="width=device-width">
<style>
body{background:#000;margin:0;display:flex;justify-content:center;align-items:center;height:100vh;overflow:hidden}
img{width:100%;height:100%;object-fit:contain;image-rendering:pixelated}
</style></head><body>
<img id="hud" src="/stream">
<div id="keys" style="position:fixed;bottom:8px;left:0;width:100%;text-align:center;color:#456;font:11px monospace;opacity:0.6">
C:Cam H:Help 1-6:Theme F1:Calibrate</div>
<script>
document.addEventListener('keydown',(e)=>{
  const map={c:'camera',h:'help','1':'blue','2':'red','3':'green','4':'amber','5':'day','6':'night',
             Escape:'escape',F1:'calibrate'};
  const cmd=map[e.key];
  if(cmd) fetch('/key/'+cmd);
});
</script>
</body></html>""")

        elif self.path.startswith("/screenshot"):
            take_screenshot()
            time.sleep(0.05)
            try:
                with open(SCREENSHOT_PATH, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/bmp")
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(404)
                self.end_headers()

        elif self.path == "/stream":
            # MJPEG stream — much faster than polling PNGs
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    take_screenshot()
                    time.sleep(0.06)  # ~16fps
                    try:
                        with open(SCREENSHOT_PATH, "rb") as f:
                            frame = f.read()
                    except Exception:
                        continue
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/png\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif self.path.startswith("/key/"):
            key = self.path.split("/key/")[1]
            cmd_map = {
                "camera": ("show", "camera"),
                "help": ("show", "help"),
                "keys": ("show", "keys"),
                "blue": ("theme", "blue"),
                "red": ("theme", "red"),
                "green": ("theme", "green"),
                "amber": ("theme", "amber"),
                "day": ("theme", "day"),
                "night": ("theme", "night"),
                "calibrate": ("system", "calibrate"),
                "escape": ("show", "home"),
            }
            if key in cmd_map:
                action, target = cmd_map[key]
                # Write to voice signal file (HUD reads this)
                try:
                    with open("/tmp/car-hud-voice-signal", "w") as f:
                        json.dump({"action": action, "target": target,
                                   "time": time.time()}, f)
                except Exception:
                    pass
                # Also write theme file directly for theme changes
                if action == "theme":
                    try:
                        with open("/home/chrismslist/northstar/.theme", "w") as f:
                            json.dump({"theme": target, "auto": False}, f)
                    except Exception:
                        pass
            self.send_response(200)
            self.end_headers()

        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = {}
            for f, k in [("/tmp/car-hud-obd-data", "obd"),
                          ("/tmp/car-hud-voice-signal", "voice"),
                          ("/tmp/car-hud-wifi-data", "wifi"),
                          ("/tmp/car-hud-mic-level", "mic")]:
                try:
                    with open(f) as fh:
                        status[k] = json.load(fh) if f.endswith(".json") or "data" in f or "signal" in f else fh.read()
                except Exception:
                    pass
            self.wfile.write(json.dumps(status).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silent


def main():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Screenshot server on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
