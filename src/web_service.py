SETTINGS_HTML = '<!DOCTYPE html>\n<html><head><title>Car-HUD Settings</title>\n<meta name="viewport" content="width=device-width">\n<style>\n*{margin:0;padding:0;box-sizing:border-box}\nbody{background:#0a0a12;color:#ccc;font-family:monospace;padding:50px 12px 12px}\nnav{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.9);padding:6px 12px;display:flex;gap:16px;z-index:10;font-size:12px}\nnav a{color:#0af;text-decoration:none}\nh2{color:#0af;margin:14px 0 6px;font-size:13px}\n.card{background:#111;border:1px solid #222;border-radius:6px;padding:10px;margin:6px 0}\n.row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:11px}\n.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}\n.g{background:#0a4}.a{background:#da0}.r{background:#d33}.d{background:#333}\nbutton{background:#0af;color:#000;border:none;padding:4px 10px;border-radius:3px;cursor:pointer;font:11px monospace}\nbutton:hover{background:#0cf}\ninput,select{background:#1a1a2a;border:1px solid #333;color:#ccc;padding:4px 8px;border-radius:3px;font:11px monospace}\n.item{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1a1a1a;font-size:11px}\n.dim{color:#567}\n#log{background:#050510;border:1px solid #1a1a1a;padding:6px;margin-top:8px;font-size:10px;max-height:80px;overflow-y:auto;border-radius:3px}\n.toggle{display:flex;align-items:center;gap:8px}\n</style></head><body>\n<nav><a href="/">HUD</a><a href="/camera">Camera</a><a href="/dashcam">Recordings</a>\n<a href="/settings">Settings</a><a href="/settings">Settings</a></nav>\n\n<h2>WiFi</h2>\n<div class="card">\n<div class="row"><span id="ws">...</span><button onclick="scanW()">Scan</button></div>\n<div id="wn"></div>\n<div class="row" style="margin-top:6px"><input id="ss" placeholder="SSID" style="width:120px"><input id="pw" placeholder="Password" type="password" style="width:120px"><button onclick="conW()">Connect</button></div>\n</div>\n\n<h2>Bluetooth</h2>\n<div class="card">\n<div class="row"><span id="bs">...</span><button onclick="scanB()">Scan</button></div>\n<div id="bd"></div>\n<div class="row toggle"><span>Audio Streaming</span><button id="aud-btn" onclick="togAud()">ON</button></div>\n</div>\n\n<h2>Theme</h2>\n<div class="card"><div class="row">\n<select id="ts" onchange="setT()">\n<option value="auto">Auto Day/Night</option>\n<option value="blue">Blue</option><option value="red">Red</option>\n<option value="green">Green</option><option value="amber">Amber</option>\n<option value="day">Day</option><option value="night">Night</option>\n</select></div></div>\n\n<h2>Widgets</h2>\n<div class="card" id="wdg">Loading...</div>\n\n<h2>System</h2>\n<div class="card" id="sys">...</div>\n\n<h2>Music</h2>\n<div class="card" id="mus">...</div>\n\n<div id="log"></div>\n\n<script>\nconst L=m=>{const l=document.getElementById(\'log\');l.innerHTML+=m+\'<br>\';l.scrollTop=9999};\nlet audOn=true;\n\nasync function load(){try{\nconst d=await(await fetch(\'/status\')).json();\nconst w=d.wifi||{};const ws=w.state||\'?\';\nconst dc=ws==\'connected\'||ws==\'tethered\'?\'g\':ws==\'connecting\'?\'a\':\'d\';\ndocument.getElementById(\'ws\').innerHTML=\'<span class="dot \'+dc+\'"></span>\'+(w.ssid||ws);\n\nlet s=\'\';\nif(d.obd){const o=d.obd;s+=\'<div class="row">OBD: <span class="dot \'+(o.connected?\'g\':\'d\')+\'"></span>\'+(o.connected?o.adapter||\'Connected\':o.status)+\'</div>\'}\nif(d.dashcam){s+=\'<div class="row">Cam: \'+(d.dashcam.recording?\'REC\':\'Idle\')+\' \'+d.dashcam.size_mb+\'MB / \'+d.dashcam.cam_count+\' cam(s)</div>\'}\ns+=\'<div class="row">Mic: \'+(d.mic||\'none\')+\'</div>\';\ndocument.getElementById(\'sys\').innerHTML=s;\n\n// Music\nconst m=d.obd;// placeholder\ntry{\nconst md=await(await fetch(\'/status\')).json();\nif(md.music){document.getElementById(\'mus\').innerHTML=md.music.playing?md.music.track+\' - \'+md.music.artist:\'Not playing\'}\n}catch(e){}\n}catch(e){}}\n\nasync function scanW(){L(\'Scanning...\');try{\nconst d=await(await fetch(\'/api/wifi/scan\')).json();\nlet h=\'\';for(const n of d)h+=\'<div class="item"><span>\'+n.ssid+\'</span><span class="dim">\'+n.signal+\'%</span></div>\';\ndocument.getElementById(\'wn\').innerHTML=h;L(d.length+\' networks\');}catch(e){L(\'Error\')}}\n\nasync function conW(){const s=document.getElementById(\'ss\').value,p=document.getElementById(\'pw\').value;\nif(!s){L(\'Enter SSID\');return}L(\'Connecting...\');\nconst r=await(await fetch(\'/api/wifi/connect\',{method:\'POST\',body:\'ssid=\'+encodeURIComponent(s)+\'&password=\'+encodeURIComponent(p)})).json();\nL(r.success?\'Connected!\':\'Failed: \'+r.msg);setTimeout(load,3000)}\n\nasync function scanB(){L(\'Scanning BT (8s)...\');\nconst d=await(await fetch(\'/api/bt/scan\')).json();\nlet h=\'\';for(const v of d)h+=\'<div class="item"><span>\'+v.name+\'</span><button onclick="pairB(\\\'\'+v.mac+\'\\\')">Pair</button></div>\';\ndocument.getElementById(\'bd\').innerHTML=h;L(d.length+\' devices\')}\n\nasync function pairB(mac){L(\'Pairing \'+mac+\'...\');\nawait fetch(\'/api/bt/pair\',{method:\'POST\',body:\'mac=\'+encodeURIComponent(mac)});L(\'Paired\')}\n\nasync function togAud(){audOn=!audOn;\nawait fetch(\'/api/bt/audio\',{method:\'POST\',body:\'enable=\'+audOn});\ndocument.getElementById(\'aud-btn\').textContent=audOn?\'ON\':\'OFF\';L(\'Audio \'+(audOn?\'enabled\':\'disabled\'))}\n\nasync function setT(){const t=document.getElementById(\'ts\').value;\nawait fetch(\'/api/theme/set\',{method:\'POST\',body:\'theme=\'+(t==\'auto\'?\'blue\':t)+\'&auto=\'+(t==\'auto\')});L(\'Theme: \'+t)}\n\nasync function loadW(){try{\nconst d=await(await fetch(\'/api/widgets\')).json();\nlet h=\'\';for(const w of d)h+=\'<div class="item"><span>\'+w.name+\' <span class="dim">(p:\'+w.priority+\')</span></span><button onclick="togW(this)" data-name="\'+w.name+\'" data-en="\'+(!w.enabled)+\'">\'+((w.enabled)?\'ON\':\'OFF\')+\'</button></div>\';\ndocument.getElementById(\'wdg\').innerHTML=h||\'No widgets\';}catch(e){document.getElementById(\'wdg\').innerHTML=\'Error\'}}\n\nasync function togW(el){var n=el.dataset.name,en=el.dataset.en;L(\'Widget \'+n+\': \'+en);\nawait fetch(\'/api/widget/set\',{method:\'POST\',body:\'name=\'+encodeURIComponent(n)+\'&enabled=\'+en});\nloadW()}\n\nload();loadW();setInterval(load,5000);\n</script></body></html>'

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
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote

PORT = 8080
SCREENSHOT_PATH = "/dev/shm/car-hud-screenshot.bmp"
DASHCAM_DIR = "/home/chrismslist/car-hud/dashcam"
DASHCAM_STATUS = "/tmp/car-hud-dashcam-data"

# Reference counting for active camera streams
STREAM_COUNT = 0
STREAM_LOCK = threading.Lock()

def start_streaming_session():
    global STREAM_COUNT
    with STREAM_LOCK:
        if STREAM_COUNT == 0:
            subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                           capture_output=True, timeout=5)
        STREAM_COUNT += 1

def stop_streaming_session():
    global STREAM_COUNT
    with STREAM_LOCK:
        STREAM_COUNT -= 1
        if STREAM_COUNT <= 0:
            STREAM_COUNT = 0
            subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                           capture_output=True, timeout=5)


def find_cameras():
    """Find all valid USB video capture devices."""
    cams = []
    try:
        r = subprocess.run(["v4l2-ctl", "--list-devices"], 
                           capture_output=True, text=True, timeout=5)
        lines = r.stdout.split("\n")
        current_bus = ""
        for line in lines:
            if ":" in line and not line.startswith("\t"):
                current_bus = line.lower()
            elif line.strip().startswith("/dev/video"):
                dev = line.strip()
                if "bcm2835" in current_bus or "unicam" in current_bus:
                    continue
                res = subprocess.run(["v4l2-ctl", "--device", dev, "--all"], 
                                      capture_output=True, text=True, timeout=2)
                if "Device Caps      : 0x04200001" in res.stdout:
                    cams.append(dev)
    except Exception:
        pass
    return sorted(list(set(cams)))


def take_screenshot():
    try:
        with open("/dev/shm/car-hud-screenshot-request", "w") as f:
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
        elif path.startswith("/camera/stream/"):
            self.serve_camera_stream(path)
        elif path == "/dashcam":
            self.serve_dashcam_page()
        elif path.startswith("/dashcam/video/"):
            self.serve_dashcam_video(path)
        elif path.startswith("/screenshot"):
            self.serve_screenshot()
        elif path.startswith("/key/"):
            self.handle_key(path)
        elif path == "/settings":
            self.serve_settings()
        elif path == "/api/wifi/scan":
            self.api_wifi_scan()
        elif path == "/api/wifi/disconnect":
            self.api_wifi_disconnect()
        elif path == "/api/bt/scan":
            self.api_bt_scan()
        elif path == "/api/theme":
            self.api_get_theme()
        elif path == "/api/widgets":
            self.api_get_widgets()
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
<a href="/camera">Cameras</a>
<a href="/dashcam">Recordings</a>\n<a href="/settings">Settings</a>
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
        
        # Check how many cameras we have
        cam_count = 1
        try:
            with open(DASHCAM_STATUS) as f:
                status = json.load(f)
                cam_count = status.get("cam_count", 1)
        except Exception:
            cam_count = len(find_cameras()) or 1

        cam_html = ""
        for i in range(cam_count):
            cam_html += f"""
            <div class="cam-box">
                <div class="cam-label">Camera {i}</div>
                <img src="/camera/stream/{i}">
            </div>"""

        html = f"""<!DOCTYPE html>
<html><head><title>Car-HUD Cameras</title>
<meta name="viewport" content="width=device-width">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;color:#fff;font-family:monospace}}
.view{{width:100vw;min-height:100vh;display:flex;flex-wrap:wrap;justify-content:center;align-items:center;padding-top:40px;gap:10px}}
.cam-box{{position:relative;flex:1;min-width:320px;max-width:640px}}
img{{width:100%;height:auto;display:block;border:1px solid #222}}
.cam-label{{position:absolute;top:5px;left:5px;background:rgba(0,0,0,0.6);padding:2px 6px;font-size:12px;color:#0af}}
nav{{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.8);padding:6px 12px;display:flex;gap:16px;z-index:10;font-size:12px}}
nav a{{color:#0af;text-decoration:none}}
.rec{{position:fixed;top:30px;left:12px;color:red;font-size:14px;animation:blink 1s infinite;z-index:11}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:0}}}}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Cameras</a>
<a href="/dashcam">Recordings</a>\n<a href="/settings">Settings</a>
</nav>
<div class="rec">&#9679; LIVE</div>
<div class="view">{cam_html}</div>
</body></html>"""
        self.wfile.write(html.encode())

    def serve_dashcam_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        # Normal chunks
        files = sorted(glob.glob(os.path.join(DASHCAM_DIR, "chunk_*.mp4")), reverse=True)
        rows = ""
        total_mb = 0
        for f in files:
            name = os.path.basename(f)
            size = os.path.getsize(f)
            total_mb += size / (1024*1024)
            cam_id = name.split("_cam")[1].split(".")[0] if "_cam" in name else "0"
            ts_part = name.replace("chunk_", "").split("_cam")[0]
            try:
                date = f"{ts_part[:4]}-{ts_part[4:6]}-{ts_part[6:8]}"
                t = f"{ts_part[9:11]}:{ts_part[11:13]}:{ts_part[13:15]}"
                display = f"{date} {t}"
            except Exception:
                display = name
            size_mb = size / (1024*1024)
            cam_label = f'<span style="color:{"#0af" if cam_id=="0" else "#f0a"}">Cam {cam_id}</span>'
            rows += f'<tr><td>{display}</td><td>{cam_label}</td><td>{size_mb:.1f} MB</td>'
            rows += f'<td><a href="/dashcam/video/{name}">Play</a> | '
            rows += f'<a href="/dashcam/video/{name}" download>Download</a></td></tr>'

        # Saved clips
        saved_dir = os.path.join(DASHCAM_DIR, "saved")
        saved_files = sorted(glob.glob(os.path.join(saved_dir, "*.mp4")), reverse=True)
        saved_rows = ""
        for f in saved_files:
            name = os.path.basename(f)
            size = os.path.getsize(f)
            cam_id = name.split("_cam")[1].split(".")[0] if "_cam" in name else "0"
            ts_part = name.replace("chunk_", "").split("_cam")[0]
            try:
                date = f"{ts_part[:4]}-{ts_part[4:6]}-{ts_part[6:8]}"
                t = f"{ts_part[9:11]}:{ts_part[11:13]}:{ts_part[13:15]}"
                display = f"{date} {t}"
            except Exception:
                display = name
            size_mb = size / (1024*1024)
            cam_label = f'<span style="color:{"#0af" if cam_id=="0" else "#f0a"}">Cam {cam_id}</span>'
            saved_rows += f'<tr style="background:rgba(0,255,100,0.05)"><td>{display}</td><td>{cam_label}</td><td>{size_mb:.1f} MB</td>'
            saved_rows += f'<td><a href="/dashcam/video/saved/{name}">Play</a> | '
            saved_rows += f'<a href="/dashcam/video/saved/{name}" download>Download</a></td></tr>'

        html = f"""<!DOCTYPE html>
<html><head><title>Dashcam Recordings</title>
<meta name="viewport" content="width=device-width">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a12;color:#ccc;font-family:monospace;padding:40px 12px 12px}}
nav{{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.9);padding:6px 12px;display:flex;gap:16px;z-index:10;font-size:12px}}
nav a{{color:#0af;text-decoration:none}}
h2{{color:#0af;margin:16px 0 8px}}
.stats{{color:#567;font-size:11px;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;margin-bottom:20px}}
th{{text-align:left;color:#0af;border-bottom:1px solid #234;padding:6px 4px;font-size:11px}}
td{{padding:6px 4px;border-bottom:1px solid #111;font-size:12px}}
a{{color:#0af}}
.saved-hdr{{color:#0f6}}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Cameras</a>
<a href="/dashcam">Recordings</a>\n<a href="/settings">Settings</a>
</nav>

<h2 class="saved-hdr">Saved Clips</h2>
<table>
<tr><th>Date/Time</th><th>Camera</th><th>Size</th><th>Actions</th></tr>
{saved_rows or '<tr><td colspan="4" style="color:#444">No saved clips</td></tr>'}
</table>

<h2>Recent Footage</h2>
<div class="stats">{len(files)} clips | {total_mb:.0f} MB total</div>
<table>
<tr><th>Date/Time</th><th>Camera</th><th>Size</th><th>Actions</th></tr>
{rows}
</table>
</body></html>"""
        self.wfile.write(html.encode())

    def serve_dashcam_video(self, path):
        # Handle saved subfolder
        is_saved = "/dashcam/video/saved/" in path
        if is_saved:
            filename = unquote(path.split("/dashcam/video/saved/")[1])
            filepath = os.path.join(DASHCAM_DIR, "saved", filename)
        else:
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

    def serve_camera_stream(self, path):
        """Live MJPEG stream from webcam via ffmpeg."""
        cam_idx = 0
        try:
            cam_idx = int(path.split("/camera/stream/")[1])
        except Exception:
            pass

        cams = find_cameras()
        if cam_idx >= len(cams):
            self.send_response(404)
            self.end_headers()
            return
        
        video_dev = cams[cam_idx]

        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        start_streaming_session()
        # Kill any existing ffmpeg processes for THIS device
        subprocess.run(["pkill", "-f", f"ffmpeg.*{video_dev}"], capture_output=True, timeout=3)
        time.sleep(0.5)

        try:
            proc = subprocess.Popen([
                "ffmpeg", "-f", "v4l2", "-video_size", "640x480",
                "-framerate", "10", "-i", video_dev,
                "-f", "mjpeg", "-q:v", "5", "-"
            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            buf = b""
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
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
            stop_streaming_session()

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
                    with open("/home/chrismslist/car-hud/.theme", "w") as f:
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
                      ("/tmp/car-hud-mic-level", "mic"),
                      ("/tmp/car-hud-music-data", "music")]:
            try:
                with open(f) as fh:
                    status[k] = json.load(fh) if "data" in f or "signal" in f else fh.read()
            except Exception:
                pass
        self.wfile.write(json.dumps(status).encode())

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        import urllib.parse
        params = urllib.parse.parse_qs(body)

        if path == "/api/wifi/connect":
            ssid = params.get("ssid", [""])[0]
            pw = params.get("password", [""])[0]
            import subprocess
            cmd = ["sudo", "nmcli", "dev", "wifi", "connect", ssid]
            if pw:
                cmd += ["password", pw]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self._json_response({"success": r.returncode == 0, "msg": (r.stdout + r.stderr).strip()})

        elif path == "/api/theme/set":
            theme = params.get("theme", ["blue"])[0]
            auto = params.get("auto", ["false"])[0] == "true"
            with open("/home/chrismslist/car-hud/.theme", "w") as f:
                json.dump({"theme": theme, "auto": auto}, f)
            self._json_response({"success": True})

        elif path == "/api/bt/pair":
            mac = params.get("mac", [""])[0]
            import subprocess
            subprocess.run(["bluetoothctl", "pair", mac], capture_output=True, timeout=15)
            subprocess.run(["bluetoothctl", "trust", mac], capture_output=True, timeout=5)
            subprocess.run(["bluetoothctl", "connect", mac], capture_output=True, timeout=10)
            self._json_response({"success": True, "mac": mac})

        elif path == "/api/widget/set":
            wname = params.get("name", [""])[0]
            enabled = params.get("enabled", ["true"])[0] == "true"
            try:
                import sys
                sys.path.insert(0, "/home/chrismslist/car-hud")
                import widgets
                widgets.set_enabled(wname, enabled)
                self._json_response({"success": True, "name": wname, "enabled": enabled})
            except Exception as e:
                self._json_response({"success": False, "error": str(e)})

        elif path == "/api/bt/audio":
            enable = params.get("enable", ["true"])[0] == "true"
            import subprocess
            if enable:
                subprocess.run(["sudo", "systemctl", "start", "raspotify"], capture_output=True, timeout=5)
            else:
                subprocess.run(["sudo", "systemctl", "stop", "raspotify"], capture_output=True, timeout=5)
            self._json_response({"success": True, "audio": enable})

        else:
            self.send_response(404)
            self.end_headers()

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    
    def serve_settings(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(SETTINGS_HTML.encode())

    def api_wifi_scan(self):
        import subprocess
        r = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"],
                           capture_output=True, text=True, timeout=15)
        nets = []
        seen = set()
        for line in r.stdout.strip().split("\n"):
            p = line.split(":")
            if len(p) >= 2 and p[0] and p[0] not in seen:
                seen.add(p[0])
                nets.append({"ssid": p[0], "signal": p[1] if len(p)>1 else "?", "security": p[2] if len(p)>2 else ""})
        self._json_response(nets[:15])

    def api_wifi_disconnect(self):
        import subprocess
        subprocess.run(["nmcli", "dev", "disconnect", "wlan0"], capture_output=True, timeout=10)
        self._json_response({"success": True})

    def api_bt_scan(self):
        import subprocess
        subprocess.run(["bluetoothctl", "scan", "on"], capture_output=True, timeout=2)
        import time; time.sleep(8)
        subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, timeout=2)
        r = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, timeout=5)
        devs = []
        for line in r.stdout.strip().split("\n"):
            p = line.split(" ", 2)
            if len(p) >= 3:
                devs.append({"mac": p[1], "name": p[2]})
        self._json_response(devs[:15])

    def api_get_theme(self):
        try:
            with open("/home/chrismslist/car-hud/.theme") as f:
                self._json_response(json.load(f))
        except:
            self._json_response({"theme": "blue", "auto": True})

    def api_get_widgets(self):
        try:
            import sys
            sys.path.insert(0, "/home/chrismslist/car-hud")
            import widgets
            self._json_response(widgets.get_all())
        except Exception as e:
            self._json_response([])

    def log_message(self, format, *args):
        pass


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Car-HUD Web on port {PORT} (Multi-threaded)")
    server.serve_forever()


if __name__ == "__main__":
    main()
