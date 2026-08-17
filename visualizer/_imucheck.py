import serial, time, re, sys
PORT='COM10'
try:
    s=serial.Serial(PORT,115200,timeout=0.2)
except Exception as e:
    print('OPEN FAIL:',e); sys.exit()
# USB-JTAG / standard reset via EN (RTS): pulse low then release
try:
    s.setDTR(False); s.setRTS(True); time.sleep(0.15); s.setRTS(False)
except Exception as e:
    print('reset toggle warn:',e)
buf=b''; end=time.time()+18
while time.time()<end:
    try:
        n=s.in_waiting
        d=s.read(n if n else 1)
        if d: buf+=d
    except: pass
s.close()
t=buf.decode('utf-8','replace')
print('=== total chars=%d ===' % len(t))
# key markers
for pat in ['IMU PROBE','online','IMU up','IMU not up','enable game','sh2_open','evt ','INVALID','hdr read']:
    hits=re.findall('(?m)^.*'+re.escape(pat)+'.*$', t)
    for h in hits[:3]: print('>>',h.strip()[:140])
# last few hb lines
hb=re.findall(r'(?m)^.*hb:.*$', t)
print('--- hb lines (last 3) ---')
for h in hb[-3:]: print(h.strip()[:160])
q=len(re.findall(r'(?m)^Q:',t)); da=len(re.findall(r'(?m)^DATA:',t))
print('--- Q:=%d  DATA:=%d ---' % (q,da))
