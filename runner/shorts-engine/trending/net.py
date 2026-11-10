"""The one place the trending stages touch plain HTTP, so tests can replace it."""
import json, os, urllib.request

UA = 'autobiz-shorts'


def get_text(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or 'utf-8', 'replace')


def get_json(url, timeout=30):
    return json.loads(get_text(url, timeout))


def get_bytes(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout) as r:
        return r.read()


def jina(url, fmt, timeout=90):
    """The page rendered by Jina Reader on its own servers (past sites that block cloud IPs): fmt 'html', or 'screenshot' (an
    image URL). Uses JINA_API_KEY: anonymous access is refused for some outlets."""
    h = {'User-Agent': UA, 'X-Return-Format': fmt, 'Authorization': f'Bearer {os.environ.get("JINA_API_KEY", "")}'}
    with urllib.request.urlopen(urllib.request.Request('https://r.jina.ai/' + url, headers=h), timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')
