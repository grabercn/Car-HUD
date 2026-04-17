SETTINGS_HTML = """<!DOCTYPE html>
<html><head><title>Car-HUD Settings</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0b0d14;--card:#12151e;--border:#1e2235;--accent:#0af;--text:#d0d4e0;--dim:#5a6080;--green:#2dcc70;--amber:#f0ad30;--red:#e74c3c}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;padding:52px 14px 20px;font-size:14px}
nav{position:fixed;top:0;left:0;width:100%;background:rgba(11,13,20,0.95);backdrop-filter:blur(10px);padding:10px 14px;display:flex;gap:20px;z-index:10;border-bottom:1px solid var(--border)}
nav a{color:var(--accent);text-decoration:none;font-weight:600;font-size:13px;opacity:0.7;transition:opacity 0.2s}
nav a:hover,nav a.active{opacity:1}
h2{color:var(--accent);margin:18px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin:6px 0;transition:border-color 0.2s}
.card:hover{border-color:#2a3050}
.row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:13px;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:8px;flex-shrink:0}
.g{background:var(--green)}.a{background:var(--amber)}.r{background:var(--red)}.d{background:#333}
button{background:var(--accent);color:#000;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font:600 12px system-ui;transition:all 0.2s}
button:hover{background:#3cf;transform:translateY(-1px)}
button:active{transform:translateY(0)}
.btn-off{background:#333;color:#888}
.btn-danger{background:var(--red);color:#fff}
input,select{background:#0a0c14;border:1px solid var(--border);color:var(--text);padding:8px 10px;border-radius:6px;font:13px system-ui;width:100%;transition:border-color 0.2s}
input:focus,select:focus{outline:none;border-color:var(--accent)}
.input-row{display:flex;gap:8px;margin-top:8px}
.input-row input{flex:1}
.item{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:13px}
.item:last-child{border-bottom:none}
.dim{color:var(--dim);font-size:11px}
.status{display:flex;align-items:center;gap:6px;font-size:13px}
#log{background:#06080e;border:1px solid var(--border);padding:8px;margin-top:12px;font-size:11px;max-height:100px;overflow-y:auto;border-radius:8px;font-family:monospace;color:var(--dim)}
.music-card{display:flex;align-items:center;gap:12px;padding:10px}
.music-card .art{width:48px;height:48px;border-radius:6px;background:#1a1d28;flex-shrink:0}
.music-card .info{flex:1;min-width:0}
.music-card .track{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.music-card .artist{color:var(--dim);font-size:12px}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Camera</a>
<a href="/dashcam">Recordings</a>
<a href="/settings" class="active">Settings</a>
<a href="/terminal">Terminal</a>
</nav>

<h2>WiFi</h2>
<div class="card">
<div class="row"><span class="status" id="ws">Loading...</span><button onclick="scanW()">Scan Networks</button></div>
<div id="wn"></div>
<div class="input-row">
<input id="ss" placeholder="Network name (SSID)">
<input id="pw" placeholder="Password" type="password">
<button onclick="conW()">Connect</button>
</div>
</div>

<h2>Bluetooth</h2>
<div class="card">
<div class="row"><span class="status" id="bs">Ready</span><button onclick="scanB()">Scan Devices</button></div>
<div id="bd"></div>
<div class="row" style="margin-top:8px">
<span>Spotify Connect (Raspotify)</span>
<button id="aud-btn" onclick="togAud()">ON</button>
</div>
</div>

<h2>Theme</h2>
<div class="card"><div class="row">
<select id="ts" onchange="setT()">
<option value="auto">Auto (Day/Night)</option>
<option value="blue">Blue</option><option value="red">Red</option>
<option value="green">Green</option><option value="amber">Amber</option>
<option value="day">Day</option><option value="night">Night</option>
</select></div></div>

<h2>Display</h2>
<div class="card">
<div class="row"><span>Brightness</span><span id="br-val">80%</span></div>
<input type="range" id="br-slider" min="1" max="100" value="80" oninput="setBr(this.value)" style="width:100%">
</div>

<h2>Widgets</h2>
<div class="card" id="wdg">Loading...</div>

<h2>System</h2>
<div class="card" id="sys">Loading...</div>

<h2>Now Playing</h2>
<div class="card" id="mus"><div class="dim">Not playing</div></div>

<div id="log"></div>

<script>
const $=id=>document.getElementById(id);
const L=m=>{const l=$('log');l.innerHTML+='<span style="color:#3a4060">'+new Date().toLocaleTimeString()+'</span> '+m+'<br>';l.scrollTop=9999};
let audOn=true;

async function load(){try{
const d=await(await fetch('/status')).json();
const w=d.wifi||{};const ws=w.state||'offline';
const dc=ws=='connected'||ws=='tethered'?'g':ws=='connecting'?'a':'d';
$('ws').innerHTML='<span class="dot '+dc+'"></span>'+(w.ssid||ws);

let s='';
if(d.obd){const o=d.obd;s+='<div class="row"><span class="status"><span class="dot '+(o.connected?'g':'d')+'"></span>OBD '+(o.connected?'Connected':'Offline')+'</span>'+(o.connected?'<span class="dim">'+o.adapter+'</span>':'')+'</div>'}
if(d.dashcam&&typeof d.dashcam==='object'){s+='<div class="row"><span>'+(d.dashcam.recording?'<span style="color:var(--red)">REC</span>':'Idle')+' &mdash; '+d.dashcam.cam_count+' cam(s)</span><span class="dim">'+Math.round(d.dashcam.size_mb||0)+' MB</span></div>'}
$('sys').innerHTML=s||'<div class="dim">All systems nominal</div>';

// Music
if(d.music&&typeof d.music==='object'&&d.music.playing){
const m=d.music;
$('mus').innerHTML='<div class="music-card"><div class="art" style="background:var(--accent);opacity:0.3"></div><div class="info"><div class="track">'+m.track+'</div><div class="artist">'+m.artist+'</div></div><span class="dim">'+(m.device||'')+'</span></div>';
}else{$('mus').innerHTML='<div class="dim" style="padding:4px">Not playing</div>'}
}catch(e){}}

async function scanW(){L('Scanning WiFi...');$('wn').innerHTML='<div class="dim" style="padding:8px">Scanning...</div>';try{
const d=await(await fetch('/api/wifi/scan')).json();
let h='';for(const n of d)h+='<div class="item"><span>'+n.ssid+'</span><span class="dim">'+n.signal+'% '+n.security+'</span></div>';
$('wn').innerHTML=h;L(d.length+' networks found');}catch(e){L('Scan failed');$('wn').innerHTML=''}}

async function conW(){const s=$('ss').value,p=$('pw').value;
if(!s){L('Enter SSID');return}L('Connecting to '+s+'...');
try{const r=await(await fetch('/api/wifi/connect',{method:'POST',body:'ssid='+encodeURIComponent(s)+'&password='+encodeURIComponent(p)})).json();
L(r.success?'Connected!':'Failed: '+r.msg);if(r.success)setTimeout(load,2000)}catch(e){L('Connection error')}}

async function scanB(){L('Scanning Bluetooth (8s)...');$('bs').innerHTML='Scanning...';$('bd').innerHTML='<div class="dim" style="padding:8px">Searching for devices...</div>';
try{const d=await(await fetch('/api/bt/scan')).json();
let h='';for(const v of d)h+='<div class="item"><span>'+v.name+'<br><span class="dim">'+v.mac+'</span></span><button onclick="pairB(this,\\''+v.mac+'\\')">Pair</button></div>';
$('bd').innerHTML=h||'<div class="dim">No devices found</div>';$('bs').innerHTML='Ready';L(d.length+' devices')}catch(e){$('bs').innerHTML='Ready';L('Scan error')}}

async function pairB(btn,mac){btn.textContent='Pairing...';btn.disabled=true;L('Pairing '+mac+'...');
try{await fetch('/api/bt/pair',{method:'POST',body:'mac='+encodeURIComponent(mac)});btn.textContent='Paired';L('Paired!')}catch(e){btn.textContent='Failed';L('Pair failed')}}

async function togAud(){audOn=!audOn;
$('aud-btn').textContent=audOn?'ON':'OFF';$('aud-btn').className=audOn?'':'btn-off';
await fetch('/api/bt/audio',{method:'POST',body:'enable='+audOn});L('Audio '+(audOn?'enabled':'disabled'))}

async function setT(){const t=$('ts').value;
await fetch('/api/theme/set',{method:'POST',body:'theme='+(t=='auto'?'blue':t)+'&auto='+(t=='auto')});L('Theme: '+t)}

async function loadW(){try{
const d=await(await fetch('/api/widgets')).json();
let h='';for(const w of d){
const cls=w.enabled?'':'btn-off';
h+='<div class="item"><span>'+w.name+'</span><button class="'+cls+'" onclick="togW(this)" data-name="'+w.name+'" data-en="'+(!w.enabled)+'">'+(w.enabled?'ON':'OFF')+'</button></div>'}
$('wdg').innerHTML=h||'<div class="dim">No widgets</div>'}catch(e){$('wdg').innerHTML='<div class="dim">Error loading</div>'}}

async function togW(el){const n=el.dataset.name,en=el.dataset.en;L('Widget '+n+': '+en);
await fetch('/api/widget/set',{method:'POST',body:'name='+encodeURIComponent(n)+'&enabled='+en});loadW()}

async function loadTheme(){try{const d=await(await fetch('/api/theme')).json();const s=$('ts');if(d.auto)s.value='auto';else if(d.theme)s.value=d.theme}catch(e){}}

async function loadBr(){try{const d=await(await fetch('/api/brightness')).json();$('br-slider').value=d.brightness;$('br-val').textContent=d.brightness+'%'}catch(e){}}

let brTimer=null;
function setBr(v){$('br-val').textContent=v+'%';clearTimeout(brTimer);brTimer=setTimeout(async()=>{await fetch('/api/brightness/set',{method:'POST',body:'level='+v});L('Brightness: '+v+'%')},200)}

load();loadW();loadTheme();loadBr();setInterval(load,4000);
</script></body></html>"""

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

import pty
import select
import fcntl
import struct
import termios

PORT = 8080
SCREENSHOT_PATH = "/dev/shm/car-hud-screenshot.bmp"
DASHCAM_DIR = "/home/chrismslist/car-hud/dashcam"
DASHCAM_STATUS = "/tmp/car-hud-dashcam-data"

# ── Terminal PTY ──
_term_fd = None
_term_pid = None
_term_buf = ""
_term_lock = threading.Lock()

def _terminal_ensure():
    """Start a bash PTY if not running."""
    global _term_fd, _term_pid
    if _term_fd is not None:
        # Check if still alive
        try:
            os.waitpid(_term_pid, os.WNOHANG)
        except ChildProcessError:
            _term_fd = None
            _term_pid = None
    if _term_fd is None:
        pid, fd = pty.fork()
        if pid == 0:
            # Child — set TERM and exec bash
            os.environ["TERM"] = "xterm"
            os.execvp("bash", ["bash", "--login"])
        else:
            _term_pid = pid
            _term_fd = fd
            # Set non-blocking
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            # Set terminal size
            winsize = struct.pack("HHHH", 30, 100, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

def _terminal_read():
    """Read available output from PTY."""
    global _term_buf
    _terminal_ensure()
    if _term_fd is None:
        return ""
    with _term_lock:
        try:
            while True:
                r, _, _ = select.select([_term_fd], [], [], 0)
                if not r:
                    break
                data = os.read(_term_fd, 4096)
                if not data:
                    break
                _term_buf += data.decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        # Keep last 8KB
        if len(_term_buf) > 8192:
            _term_buf = _term_buf[-8192:]
        return _term_buf

def _terminal_write(text):
    """Write input to PTY."""
    _terminal_ensure()
    if _term_fd is None:
        return
    with _term_lock:
        try:
            os.write(_term_fd, text.encode())
        except (OSError, IOError):
            pass

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
        elif path == "/terminal":
            self.serve_terminal_page()
        elif path == "/api/terminal/read":
            self.api_terminal_read()
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
        elif path == "/api/brightness":
            self.api_get_brightness()
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
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#fff;font-family:system-ui,sans-serif}
.view{width:100vw;height:100vh;display:flex;justify-content:center;align-items:center}
img{width:100%;height:100%;object-fit:contain;image-rendering:pixelated}
nav{position:fixed;top:0;left:0;width:100%;background:rgba(0,0,0,0.9);backdrop-filter:blur(10px);padding:10px 14px;display:flex;gap:20px;z-index:10;border-bottom:1px solid #1e2235}
nav a{color:#0af;text-decoration:none;font-weight:600;font-size:13px;opacity:0.7;transition:opacity 0.2s}
nav a:hover,nav a.active{opacity:1}
</style></head><body>
<nav>
<a href="/" class="active">HUD</a>
<a href="/camera">Camera</a>
<a href="/dashcam">Recordings</a>
<a href="/settings">Settings</a>
<a href="/terminal">Terminal</a>
</nav>
<div class="view" style="padding-top:36px"><img id="hud" src="/stream"></div>
<script>
document.addEventListener('keydown',e=>{
  const map={c:'camera',h:'help','1':'blue','2':'red','3':'green','4':'amber','5':'day','6':'night',Escape:'escape',F1:'calibrate'};
  if(map[e.key]) fetch('/key/'+map[e.key]);
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
<a href="/terminal">Terminal</a>
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
<a href="/terminal">Terminal</a>
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        status = {}
        json_files = {
            "/tmp/car-hud-obd-data": "obd",
            "/tmp/car-hud-wifi-data": "wifi",
            "/tmp/car-hud-dashcam-data": "dashcam",
            "/tmp/car-hud-music-data": "music",
            "/tmp/car-hud-voice-signal": "voice",
        }
        text_files = {
            "/tmp/car-hud-mic-level": "mic",
        }
        for f, k in json_files.items():
            try:
                with open(f) as fh:
                    status[k] = json.load(fh)
            except Exception:
                pass
        for f, k in text_files.items():
            try:
                with open(f) as fh:
                    status[k] = fh.read().strip()
            except Exception:
                pass
        self.wfile.write(json.dumps(status).encode())

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        import urllib.parse
        params = urllib.parse.parse_qs(body)

        if path == "/api/terminal/write":
            cmd = params.get("cmd", [""])[0]
            _terminal_write(cmd)
            self._json_response({"ok": True})
            return

        if path == "/api/brightness/set":
            level = int(params.get("level", ["80"])[0])
            try:
                with open("/home/chrismslist/car-hud/.brightness", "w") as f:
                    json.dump({"brightness": max(0, min(100, level))}, f)
                # Signal the display service
                with open("/tmp/car-hud-voice-signal", "w") as f:
                    json.dump({"action": "brightness", "target": str(level), "time": time.time()}, f)
                self._json_response({"success": True, "brightness": level})
            except Exception as e:
                self._json_response({"success": False, "error": str(e)})
            return

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

    def serve_terminal_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>Car-HUD Terminal</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0b0d14;--card:#12151e;--border:#1e2235;--accent:#0af;--green:#2dcc70}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:#d0d8e8;font-family:monospace;display:flex;flex-direction:column;height:100vh}
nav{background:rgba(11,13,20,0.95);backdrop-filter:blur(10px);padding:10px 14px;display:flex;gap:20px;border-bottom:1px solid var(--border);flex-shrink:0}
nav a{color:var(--accent);text-decoration:none;font:600 13px system-ui;opacity:0.7;transition:opacity 0.2s}
nav a:hover,nav a.active{opacity:1}
#term{flex:1;background:#000;padding:10px;overflow-y:auto;white-space:pre-wrap;word-wrap:break-word;font-size:13px;line-height:1.4;color:#c8d0e0}
#term .prompt{color:var(--green)}
#term .err{color:#e74c3c}
.input-bar{display:flex;gap:0;border-top:1px solid var(--border);flex-shrink:0}
.input-bar input{flex:1;background:#0a0c14;border:none;color:#fff;padding:12px 14px;font:14px monospace;outline:none}
.input-bar button{background:var(--accent);color:#000;border:none;padding:12px 18px;font:600 13px system-ui;cursor:pointer}
.input-bar button:hover{background:#3cf}
.toolbar{display:flex;gap:6px;padding:6px 10px;background:#0a0c12;border-top:1px solid var(--border);flex-shrink:0}
.toolbar button{background:#1a1d28;color:#888;border:1px solid var(--border);padding:4px 10px;border-radius:4px;font:11px monospace;cursor:pointer}
.toolbar button:hover{color:#fff;border-color:#444}
</style></head><body>
<nav>
<a href="/">HUD</a>
<a href="/camera">Camera</a>
<a href="/dashcam">Recordings</a>
<a href="/settings">Settings</a>
<a href="/terminal" class="active">Terminal</a>
</nav>
<div id="term"></div>
<div class="toolbar">
<button onclick="send('\\n')">Enter</button>
<button onclick="send('\\x03')">Ctrl+C</button>
<button onclick="send('q\\n')">q</button>
<button onclick="send('sudo systemctl restart car-hud\\n')">Restart HUD</button>
<button onclick="send('sudo systemctl status car-hud --no-pager\\n')">HUD Status</button>
<button onclick="send('journalctl -u car-hud --no-pager -n 20\\n')">Logs</button>
<button onclick="send('htop -d 20\\n')">htop</button>
<button onclick="send('df -h /\\n')">Disk</button>
<button onclick="send('free -h\\n')">Mem</button>
<button onclick="send('sudo reboot\\n')">Reboot</button>
<button onclick="send('clear\\n')">Clear</button>
</div>
<div class="input-bar">
<input id="cmd" placeholder="Type command..." autofocus>
<button onclick="exec()">Run</button>
</div>
<script>
const term=document.getElementById('term');
const inp=document.getElementById('cmd');
let lastLen=0;

function send(t){
fetch('/api/terminal/write',{method:'POST',body:'cmd='+encodeURIComponent(t)});
}

function exec(){
const c=inp.value;
if(!c)return;
send(c+'\\n');
inp.value='';
inp.focus();
}

inp.addEventListener('keydown',e=>{
if(e.key==='Enter')exec();
else if(e.key==='Tab'){e.preventDefault();send('\\t')}
else if(e.key==='ArrowUp'){e.preventDefault();send('\\x1b[A')}
else if(e.key==='ArrowDown'){e.preventDefault();send('\\x1b[B')}
else if(e.key==='c'&&e.ctrlKey){e.preventDefault();send('\\x03')}
else if(e.key==='d'&&e.ctrlKey){e.preventDefault();send('\\x04')}
else if(e.key==='l'&&e.ctrlKey){e.preventDefault();send('\\x0c')}
});

async function poll(){
try{
const r=await fetch('/api/terminal/read');
const d=await r.json();
if(d.output&&d.output.length!==lastLen){
lastLen=d.output.length;
// Basic ANSI strip for display
let txt=d.output.replace(/\\x1b\\[[0-9;]*[a-zA-Z]/g,'');
term.textContent=txt;
term.scrollTop=term.scrollHeight;
}
}catch(e){}
}

setInterval(poll,300);
poll();
inp.focus();
</script></body></html>""")

    def api_terminal_read(self):
        output = _terminal_read()
        self._json_response({"output": output})

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

    def api_get_brightness(self):
        try:
            with open("/tmp/car-hud-display-data") as f:
                self._json_response(json.load(f))
        except Exception:
            self._json_response({"brightness": 80})

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
