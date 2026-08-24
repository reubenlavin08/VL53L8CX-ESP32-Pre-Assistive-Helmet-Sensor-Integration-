"""Iris launcher: the always-on front door for the phone app.

Owns port 8123 permanently. When cv_fusion is running (internal port
8125) every request is proxied through untouched -- the phone app works
exactly as before. When it's not running, the same address serves a
Start page; tapping Start spawns cv_fusion and the page auto-reloads
into the live dashboard when it's up.

Run at login (a Startup shortcut is created by --install-startup) so the
home-screen icon always answers.
"""

import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = pathlib.Path(__file__).resolve().parent
PORT = 8123
INNER = 8125          # cv_fusion's --serve port
_child = None

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
 body{height:100vh;background:#101216;color:#e8e6e0;display:flex;
      flex-direction:column;align-items:center;justify-content:center;
      gap:26px;font-family:-apple-system,system-ui,sans-serif}
 h1{font-weight:600;font-size:28px;letter-spacing:.04em}
 #s{color:#8a94a6;font-size:15px;min-height:22px}
 button{background:#2456c4;border:0;color:#fff;border-radius:999px;
        padding:20px 64px;font-size:22px;font-weight:700}
 button:active{background:#1a3f92}
 button[disabled]{background:#333a45;color:#8a94a6}
</style></head><body>
<h1>Iris</h1>
<div id="s">not running</div>
<button id="b" onclick="go()">Start</button>
<script>
const S=document.getElementById('s'),B=document.getElementById('b');
async function up(){try{
 const r=await fetch('/status',{cache:'no-store'});
 const j=await r.json();return 'said' in j;
}catch(e){return false}}
async function go(){
 B.disabled=true;S.textContent='starting\\u2026';
 await fetch('/launch');
 for(let i=0;i<40;i++){
  await new Promise(r=>setTimeout(r,1000));
  if(await up()){location.reload();return}
  S.textContent='starting\\u2026 '+(i+1)+'s';
 }
 S.textContent='failed to start \\u2014 check the computer';B.disabled=false;
}
up().then(u=>{if(u)location.reload()});
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

    def do_GET(self):
        if self.path == "/launch":
            _launch()
            self._send(b"{}", "application/json")
            return
        # proxy to cv_fusion when it's up
        if _inner_alive():
            try:
                r = urllib.request.urlopen(
                    f"http://127.0.0.1:{INNER}{self.path}", timeout=25)
                self._send(r.read(), r.headers.get(
                    "Content-Type", "application/octet-stream"))
                return
            except OSError:
                pass
        # fallback: launcher's own pages
        if self.path == "/manifest.json":
            self._send(MANIFEST, "application/manifest+json")
        elif self.path == "/icon.png":
            self._send(_icon(), "image/png")
        elif self.path == "/status":
            self._send(b'{"down":true}', "application/json")
        else:
            self._send(START_PAGE.encode(), "text/html")


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
    print(f"Iris launcher on :{PORT} (inner :{INNER})")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
