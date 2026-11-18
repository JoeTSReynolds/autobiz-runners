import time, urllib.error, urllib.request

MAX_WAIT = 15   # seconds; a 429 asking longer is raised


def fetch(url, headers=None, timeout=30):
    for attempt in range(4):  # rate-limited servers (429): wait as asked, then retry
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            wait = int(e.headers.get("Retry-After") or 5 * (attempt + 1))
            if wait > MAX_WAIT:   # a long wait (Commons thumbnails ask 120 s) costs more than skipping the file
                raise
            time.sleep(wait)
