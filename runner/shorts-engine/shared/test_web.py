# web.fetch: GET with a retry when the server says 429. Run: python3 shared/test_web.py
import sys, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import web  # noqa: E402

class Resp:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self): return self.body
def err(code, retry_after=None):
    return urllib.error.HTTPError('u', code, 'x', {'Retry-After': retry_after} if retry_after else {}, None)
def fake(answers):
    calls, naps = [], []
    def urlopen(req, timeout=None):
        calls.append((req.full_url, req.get_header('User-agent'), timeout))
        a = answers.pop(0)
        if isinstance(a, Exception): raise a
        return Resp(a)
    web.urllib.request.urlopen, web.time.sleep = urlopen, naps.append
    return calls, naps

calls, naps = fake([b'hi'])
assert web.fetch('http://x', {'User-Agent': 'ua'}, 7) == b'hi' and calls == [('http://x', 'ua', 7)] and naps == [], (calls, naps)
calls, naps = fake([err(429, '2'), err(429), b'ok'])
assert web.fetch('http://x') == b'ok' and naps == [2, 10], naps  # Retry-After if given, else 5 * (attempt + 1)
calls, naps = fake([err(429)] * 4)
try: web.fetch('http://x')
except urllib.error.HTTPError as e: assert e.code == 429 and len(calls) == 4 and naps == [5, 10, 15], (len(calls), naps)
else: raise AssertionError('4th 429 must raise')
calls, naps = fake([err(404)])
try: web.fetch('http://x')
except urllib.error.HTTPError as e: assert e.code == 404 and len(calls) == 1 and not naps
else: raise AssertionError('non-429 must raise at once')
print('ok')
