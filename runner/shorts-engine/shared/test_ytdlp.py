# ytdlp.run: cookies and blocked-address reset for every yt-dlp call in the engine. Run: python3 shared/test_ytdlp.py
import os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import ytdlp  # noqa: E402

seen = []
ytdlp.subprocess.run = lambda cmd, **kw: seen.append(cmd)
os.environ.pop('YTDLP_COOKIES_FILE', None)
ytdlp.run(['-F', 'x'])
assert seen[-1] == ['yt-dlp', '-F', 'x'], seen
os.environ['YTDLP_COOKIES_FILE'] = '/tmp/c.txt'
ytdlp.run(['-F', 'x'])
assert seen[-1] == ['yt-dlp', '--cookies', '/tmp/c.txt', '-F', 'x'], seen
ytdlp.run(['--cookies', 'mine', 'x'])
assert seen[-1] == ['yt-dlp', '--cookies', 'mine', 'x'], seen

# a blocked yt-dlp call (HTTP 429 or bot check) gets a fresh address from AUTOBIZ_NETWORK_RESET_COMMAND and is retried, twice at most
class R:
    def __init__(self, code, err=''): self.returncode, self.stdout, self.stderr = code, '', err
def fake(answers):
    calls = []
    def run(cmd, **kw):
        calls.append(cmd)
        return R(0) if cmd[:2] == ['bash', '-c'] else answers.pop(0) if len(answers) > 1 else answers[0]
    ytdlp.subprocess.run = run
    return calls
os.environ.pop('YTDLP_COOKIES_FILE', None)
os.environ['AUTOBIZ_NETWORK_RESET_COMMAND'] = 'warp rotate'
calls = fake([R(1, "ERROR: Unable to download video subtitles for 'en': HTTP Error 429: Too Many Requests")])
r = ytdlp.run(['x'], capture_output=True, text=True)
assert calls == [['yt-dlp', 'x'], ['bash', '-c', 'warp rotate']] * 2 + [['yt-dlp', 'x']] and r.returncode == 1, calls
calls = fake([R(1, "Sign in to confirm you\u2019re not a bot"), R(0)])
assert ytdlp.run(['x'], capture_output=True, text=True).returncode == 0 and len(calls) == 3, calls  # stops once it works
calls = fake([R(1, 'ERROR: Video unavailable')])
ytdlp.run(['x'], capture_output=True, text=True)
assert calls == [['yt-dlp', 'x']], calls  # other errors are not the address's fault
del os.environ['AUTOBIZ_NETWORK_RESET_COMMAND']
calls = fake([R(1, 'HTTP Error 429')])
ytdlp.run(['x'], capture_output=True, text=True)
assert calls == [['yt-dlp', 'x']], calls  # no reset command (local runs): one try, as before
print('ok')
