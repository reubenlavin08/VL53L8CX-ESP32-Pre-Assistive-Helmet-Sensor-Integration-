"""Iris launcher: the always-on front door for the phone app.

Owns port 8123 permanently. Request routing, in order:
  1. local cv_fusion (internal port 8125) alive  -> proxy to it
  2. the PEER machine's launcher reports a live cv_fusion -> proxy to it
     (so ONE home-screen icon works no matter which machine runs Iris)
  3. neither -> Start page with a button per machine

Run at login (a Startup entry is created by --install-startup) so the
home-screen icon always answers.
"""

import json
import pathlib
import platform
import subprocess
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = pathlib.Path(__file__).resolve().parent
PORT = 8123
INNER = 8125          # cv_fusion's --serve port
_child = None

# two-machine fleet: each launcher knows the other one
_FLEET = {"Reubens-Laptop": ("192.168.1.223", "Zenbook"),
          "Lenovo": ("192.168.1.242", "gaming laptop")}
_me = platform.node()
PEER_IP, PEER_NAME = next(
    (v for k, v in _FLEET.items() if k != _me), ("", "other machine"))
_peer_cache = {"t": 0.0, "up": False}

MANIFEST = json.dumps({
    "name": "Iris", "short_name": "Iris", "display": "standalone",
    "orientation": "portrait", "background_color": "#101216",
    "theme_color": "#101216", "start_url": "/",
    "icons": [{"src": "/icon.png", "sizes": "512x512",
               "type": "image/png"}]}).encode()

START_PAGE = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.png">
<title>Iris</title>
<style>
 *{margin:0;box-sizing:border-box}
 body{height:100vh;color:#e8e6e0;display:flex;overflow:hidden;
      flex-direction:column;align-items:center;justify-content:center;
      gap:20px;font-family:-apple-system,system-ui,sans-serif;
      background:radial-gradient(120vmax 120vmax at 50% 120%,
        #1a1f2b 0%,#101216 55%,#0a0c10 100%)}
 /* the iris: spinning conic ring + breathing pupil */
 #eye{position:relative;width:150px;height:150px;margin-bottom:6px}
 #ring{position:absolute;inset:0;border-radius:50%;
   background:conic-gradient(from 0deg,#3c78dc,#c8a03c,#7a4fd0,#3c78dc);
   -webkit-mask:radial-gradient(circle,transparent 58%,#000 60%,#000 97%,transparent 99%);
   mask:radial-gradient(circle,transparent 58%,#000 60%,#000 97%,transparent 99%);
   animation:spin 14s linear infinite;filter:drop-shadow(0 0 18px rgba(90,130,220,.35))}
 .starting #ring{animation-duration:1.6s}
 #pupil{position:absolute;inset:31%;border-radius:50%;
   background:radial-gradient(circle at 38% 32%,#2b3550 0%,#12151d 60%,#0a0c10 100%);
   box-shadow:inset 0 0 14px #000,0 0 26px rgba(80,120,210,.25);
   animation:breathe 3.6s ease-in-out infinite}
 @keyframes spin{to{transform:rotate(360deg)}}
 @keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(.9)}}
 h1{font-weight:200;font-size:34px;letter-spacing:.42em;
    text-indent:.42em;color:#e8e6e0}
 #s{color:#8a94a6;font-size:15px;min-height:22px;text-align:center}
 button{border:0;color:#fff;border-radius:999px;min-width:264px;
        padding:17px 48px;font-size:18px;font-weight:650;
        background:linear-gradient(135deg,#2456c4,#3a6ede);
        box-shadow:0 6px 24px rgba(36,86,196,.35)}
 button.alt{background:rgba(28,32,39,.8);border:1px solid #333a45;
        box-shadow:none;color:#c4c9d4}
 button:active{transform:scale(.97)}
 button[disabled]{background:#333a45;color:#8a94a6;border:0;box-shadow:none}
</style></head><body>
<div id="eye"><div id="ring"></div><div id="pupil"></div></div>
<h1>IRIS</h1>
<div id="s">not running on either machine</div>
<button id="b0" onclick="go('')">Start on __ME__</button>
<button id="b1" class="alt" onclick="go('?peer=1')">Start on __PEER__</button>
<script>
const S=document.getElementById('s');
async function up(){try{
 const r=await fetch('/status',{cache:'no-store'});
 const j=await r.json();return 'said' in j;
}catch(e){return false}}
async function go(q){
 for(const b of document.querySelectorAll('button'))b.disabled=true;
 document.body.classList.add('starting');
 S.textContent='starting\\u2026';
 await fetch('/launch'+q);
 for(let i=0;i<40;i++){
  await new Promise(r=>setTimeout(r,1000));
  if(await up()){location.reload();return}
  S.textContent='starting\\u2026 '+(i+1)+'s';
 }
 S.textContent='failed to start \\u2014 check that computer';
 document.body.classList.remove('starting');
 for(const b of document.querySelectorAll('button'))b.disabled=false;
}
up().then(u=>{if(u)location.reload()});
setInterval(async()=>{if(await up())location.reload()},5000);
</script></body></html>"""


def _icon():
    p = _HERE / "launcher_icon.png"
    if not p.exists():
        import cv2
        import numpy as np
        ic = np.zeros((512, 512, 3), np.uint8)
        ic[:] = (24, 18, 16)
        cv2.circle(ic, (256, 256), 200, (140, 90, 30), -1, cv2.LINE_AA)
        cv2.circle(ic, (256, 256), 200, (220, 170, 60), 14, cv2.LINE_AA)
        cv2.circle(ic, (256, 256), 90, (30, 24, 20), -1, cv2.LINE_AA)
        cv2.circle(ic, (310, 200), 34, (250, 240, 230), -1, cv2.LINE_AA)
        cv2.imwrite(str(p), ic)
    return p.read_bytes()


def _inner_alive():
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{INNER}/status", timeout=1).read()
        return True
    except OSError:
        return False


def _peer_alive():
    """Does the peer's launcher have a LIVE cv_fusion behind it?  Its
    /status only contains "said" when proxying a real instance, so this
    cannot loop: we never forward to a peer that is itself falling back."""
    if not PEER_IP:
        return False
    now = time.monotonic()
    if now - _peer_cache["t"] < 3.0:
        return _peer_cache["up"]
    up = False
    try:
        body = urllib.request.urlopen(
            f"http://{PEER_IP}:{PORT}/status", timeout=1).read()
        up = b'"said"' in body
    except OSError:
        pass
    _peer_cache.update(t=now, up=up)
    return up


def _launch():
    global _child
    if _inner_alive():
        return
    if _child is not None and _child.poll() is None:
        return
    _child = subprocess.Popen(
        [sys.executable, str(_HERE / "cv_fusion.py"), "--serve", str(INNER)],
        cwd=str(_HERE),
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    print(f"launched cv_fusion pid={_child.pid}")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, base):
        try:
            r = urllib.request.urlopen(f"{base}{self.path}", timeout=25)
            self._send(r.read(), r.headers.get(
                "Content-Type", "application/octet-stream"))
            return True
        except OSError:
            return False

    def do_GET(self):
        if self.path.startswith("/launch"):
            if "peer=1" in self.path and PEER_IP:
                try:
                    urllib.request.urlopen(
                        f"http://{PEER_IP}:{PORT}/launch", timeout=3).read()
                except OSError:
                    pass
            else:
                _launch()
            self._send(b"{}", "application/json")
            return
        # 1) local cv_fusion, 2) the other machine's, 3) our own pages
        if _inner_alive() and self._proxy(f"http://127.0.0.1:{INNER}"):
            return
        if _peer_alive() and self._proxy(f"http://{PEER_IP}:{PORT}"):
            return
        if self.path == "/manifest.json":
            self._send(MANIFEST, "application/manifest+json")
        elif self.path == "/icon.png":
            self._send(_icon(), "image/png")
        elif self.path == "/status":
            self._send(b'{"down":true}', "application/json")
        else:
            page = (START_PAGE
                    .replace("__ME__", "this computer" if not PEER_IP
                             else {"Reubens-Laptop": "Zenbook",
                                   "Lenovo": "gaming laptop"}.get(
                                       _me, _me))
                    .replace("__PEER__", PEER_NAME))
            self._send(page.encode(), "text/html")


def install_startup():
    """Create a Startup-folder shortcut so the launcher runs at login."""
    startup = (pathlib.Path.home() / "AppData/Roaming/Microsoft/Windows"
               / "Start Menu/Programs/Startup")
    bat = startup / "iris_launcher.bat"
    bat.write_text(
        f'@echo off\nstart "iris-launcher" /min "{sys.executable}" '
        f'"{_HERE / "launcher.py"}"\n')
    print(f"startup entry: {bat}")


if __name__ == "__main__":
    if "--install-startup" in sys.argv:
        install_startup()
        sys.exit(0)
    print(f"Iris launcher on :{PORT} (inner :{INNER}, "
          f"peer {PEER_NAME}@{PEER_IP or 'none'})")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
