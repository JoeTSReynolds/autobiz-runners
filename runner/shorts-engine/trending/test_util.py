# yt-dlp cookies injection in util.run. Run: python3 test_util.py
import os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import util

seen = []
util.subprocess.run = lambda cmd, **kw: seen.append(cmd)
os.environ.pop('YTDLP_COOKIES_FILE', None)
util.run(['yt-dlp', '-F', 'x'])
assert seen[-1] == ['yt-dlp', '-F', 'x'], seen
os.environ['YTDLP_COOKIES_FILE'] = '/tmp/c.txt'
util.run(['yt-dlp', '-F', 'x'])
assert seen[-1] == ['yt-dlp', '--cookies', '/tmp/c.txt', '-F', 'x'], seen
util.run(['yt-dlp', '--cookies', 'mine', 'x'])
assert seen[-1] == ['yt-dlp', '--cookies', 'mine', 'x'], seen
util.run(['ffmpeg', '-i', 'x'])
assert seen[-1] == ['ffmpeg', '-i', 'x'], seen
print('ok')
