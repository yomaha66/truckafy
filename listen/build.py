import glob, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob('*.mp3'), key=os.path.getmtime, reverse=True)
rows = ''.join('<div style="margin:18px 0"><b style="font-size:20px">%s</b><br><audio controls preload="auto" src="%s?v=%d" style="width:100%%"></audio></div>' % (f, f, int(os.path.getmtime(f))) for f in files)
open('index.html','w').write('<!doctype html><meta name=viewport content="width=device-width"><meta http-equiv="Cache-Control" content="no-store"><body style="font-family:sans-serif;max-width:700px;margin:24px auto;padding:0 16px"><h2>TRUCK-A-FY listening room</h2>' + rows + '</body>')
print(files)
