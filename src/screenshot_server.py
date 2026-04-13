#!/usr/bin/env python3
"""Car-HUD Web Server
- Live HUD stream (MJPEG)
- Live camera feed (MJPEG from webcam)
- Dashcam footage browser + download
- Keyboard shortcuts
- Status API
"""

import os
import time
import json
import glob
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

PORT = 8080
SCREENSHOT_PATH = "/tmp/car-hud-screenshot.bmp"
DASHCAM_DIR = "/home/chrismslist/northstar/dashcam"
VIDEO_DEV = "/dev/video0"


def take_screenshot():
    try:
        with open("/tmp/car-hud-screenshot-request", "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/" or path == "/index.html":
            self.serve_html()
        elif path == "/stream":
            self.serve_hud_stream()
        elif path == "/camera":
            self.serve_camera_page()
        elif path == "/camera/stream":
            self.serve_camera_stream()
        elif path == "/dashcam":
            self.serve_dashcam_page()
        elif path.startswith("/dashcam/video/"):
            self.serve_dashcam_video(path)
        elif path.startswith("/screenshot"):
            self.serve_screenshot()
        elif path.startswith("/key/"):
            self.handle_key(path)
        elif path == "/status":
            self.serve_status()
        else:
            self.send_response(404)
            self.end_headers()

    def serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>Car-HUD</title>
<meta name="viewport" content="width=device-width">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#fff;font-family:monospace}
.view{width:100vw;height:100vh;display:flex;justify-content:center;align-items:center}
img{width:100%;height:100%;object-fit:contain;image-rendering:pixelated}
nav{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.8);padding:6px 12px;display:flex;gap:16px;z-index:10;font-size:12px}
nav a{color:#0af;text-decoration:none}
nav a:hover{color:#fff}
.keys{position:fixed;bottom:6px;left:0;width:100%;text-align:center;color:#345;font-size:10px}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Camera</a>
<a href="/dashcam">Recordings</a>
</nav>
<div class="view" style="padding-top:24px"><img id="hud" src="/stream"></div>
<div class="keys">C:Cam H:Help 1-6:Theme ESC:Close</div>
<script>
document.addEventListener('keydown',(e)=>{
  const map={c:'camera',h:'help','1':'blue','2':'red','3':'green','4':'amber','5':'day','6':'night',
             Escape:'escape',F1:'calibrate'};
  const cmd=map[e.key];
  if(cmd) fetch('/key/'+cmd);
});
</script>
</body></html>""")

    def serve_camera_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>Car-HUD Camera</title>
<meta name="viewport" content="width=device-width">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#fff;font-family:monospace}
.view{width:100vw;height:100vh;display:flex;justify-content:center;align-items:center}
img{width:100%;height:100%;object-fit:contain}
nav{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.8);padding:6px 12px;display:flex;gap:16px;z-index:10;font-size:12px}
nav a{color:#0af;text-decoration:none}
nav a:hover{color:#fff}
.rec{position:fixed;top:30px;left:12px;color:red;font-size:14px;animation:blink 1s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Camera</a>
<a href="/dashcam">Recordings</a>
</nav>
<div class="rec">&#9679; LIVE</div>
<div class="view"><img src="/camera/stream"></div>
</body></html>""")

    def serve_dashcam_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        files = sorted(glob.glob(os.path.join(DASHCAM_DIR, "chunk_*.mp4")), reverse=True)
        rows = ""
        total_mb = 0
        for f in files:
            name = os.path.basename(f)
            size = os.path.getsize(f)
            total_mb += size / (1024*1024)
            # Parse timestamp from filename: chunk_YYYYMMDD_HHMMSS.mp4
            ts = name.replace("chunk_", "").replace(".mp4", "")
            try:
                date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                t = f"{ts[9:11]}:{ts[11:13]}:{ts[13:15]}"
                display = f"{date} {t}"
            except Exception:
                display = name
            size_mb = size / (1024*1024)
            rows += f'<tr><td>{display}</td><td>{size_mb:.1f} MB</td>'
            rows += f'<td><a href="/dashcam/video/{name}">Play</a> | '
            rows += f'<a href="/dashcam/video/{name}" download>Download</a></td></tr>'

        html = f"""<!DOCTYPE html>
<html><head><title>Dashcam Recordings</title>
<meta name="viewport" content="width=device-width">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a12;color:#ccc;font-family:monospace;padding:40px 12px 12px}}
nav{{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.9);padding:6px 12px;display:flex;gap:16px;z-index:10;font-size:12px}}
nav a{{color:#0af;text-decoration:none}}
h2{{color:#0af;margin:8px 0}}
.stats{{color:#567;font-size:11px;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;color:#0af;border-bottom:1px solid #234;padding:6px 4px;font-size:11px}}
td{{padding:6px 4px;border-bottom:1px solid #111;font-size:12px}}
a{{color:#0af}}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Camera</a>
<a href="/dashcam">Recordings</a>
</nav>
<h2>Dashcam Recordings</h2>
<div class="stats">{len(files)} clips | {total_mb:.0f} MB total | 2GB max</div>
<table>
<tr><th>Date/Time</th><th>Size</th><th>Actions</th></tr>
{rows}
</table>
</body></html>"""
        self.wfile.write(html.encode())

    def serve_dashcam_video(self, path):
        filename = unquote(path.split("/dashcam/video/")[1])
        filepath = os.path.join(DASHCAM_DIR, filename)
        if not os.path.exists(filepath) or ".." in filename:
            self.send_response(404)
            self.end_headers()
            return

        size = os.path.getsize(filepath)
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.end_headers()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def serve_hud_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                take_screenshot()
                time.sleep(0.06)
                try:
                    with open(SCREENSHOT_PATH, "rb") as f:
                        frame = f.read()
                except Exception:
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/bmp\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def serve_camera_stream(self):
        """Live MJPEG stream from webcam via ffmpeg."""
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        # Need to stop dashcam briefly to access camera
        subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                       capture_output=True, timeout=5)
        subprocess.run(["pkill", "-f", "ffmpeg.*video0"], capture_output=True, timeout=3)
        time.sleep(0.5)

        try:
            proc = subprocess.Popen([
                "ffmpeg", "-f", "v4l2", "-video_size", "640x480",
                "-framerate", "10", "-i", VIDEO_DEV,
                "-f", "mjpeg", "-q:v", "5", "-"
            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            buf = b""
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
                # Find JPEG frames (start with FFD8, end with FFD9)
                while True:
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2)
                    if start == -1 or end == -1:
                        break
                    jpg = buf[start:end + 2]
                    buf = buf[end + 2:]
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode())
                    self.wfile.write(jpg)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                           capture_output=True, timeout=5)

    def serve_screenshot(self):
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

    def handle_key(self, path):
        key = path.split("/key/")[1]
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
            try:
                with open("/tmp/car-hud-voice-signal", "w") as f:
                    json.dump({"action": action, "target": target,
                               "time": time.time()}, f)
            except Exception:
                pass
            if action == "theme":
                try:
                    with open("/home/chrismslist/northstar/.theme", "w") as f:
                        json.dump({"theme": target, "auto": False}, f)
                except Exception:
                    pass
        self.send_response(200)
        self.end_headers()

    def serve_status(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        status = {}
        for f, k in [("/tmp/car-hud-obd-data", "obd"),
                      ("/tmp/car-hud-voice-signal", "voice"),
                      ("/tmp/car-hud-wifi-data", "wifi"),
                      ("/tmp/car-hud-dashcam-data", "dashcam"),
                      ("/tmp/car-hud-mic-level", "mic")]:
            try:
                with open(f) as fh:
                    status[k] = json.load(fh) if "data" in f or "signal" in f else fh.read()
            except Exception:
                pass
        self.wfile.write(json.dumps(status).encode())

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Car-HUD Web on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
