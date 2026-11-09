"""The one place the trending stages touch plain HTTP, so tests can replace it."""
import json, urllib.request

UA = 'autobiz-shorts'


def get_text(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or 'utf-8', 'replace')


def get_json(url, timeout=30):
    return json.loads(get_text(url, timeout))
