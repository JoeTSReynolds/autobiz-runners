# media.duration: seconds of an audio/video file via ffprobe. Run: python3 shared/test_media.py
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import media  # noqa: E402

seen = []
class R:
    stdout = '12.5\n'
media.subprocess.run = lambda cmd, **kw: seen.append((cmd, kw)) or R()
assert media.duration(Path('/x/a.mp3')) == 12.5
assert seen[-1][0] == ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', '/x/a.mp3'], seen
assert seen[-1][1].get('check') is True, 'a failed ffprobe raises'
print('ok')
