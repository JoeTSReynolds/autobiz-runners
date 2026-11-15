import time, urllib.error, urllib.request


def fetch(url, headers=None, timeout=30):
    for attempt in range(4):  # rate-limited servers (429): wait as asked, then retry
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 5 * (attempt + 1)))
