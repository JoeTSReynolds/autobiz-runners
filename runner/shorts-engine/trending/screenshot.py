"""Python wrapper for screenshot.mjs (Node + Playwright). Both return the PNG path, or None if the shot failed."""
import json, subprocess
from pathlib import Path

MJS = str(Path(__file__).with_name('screenshot.mjs'))


def _run(*args, timeout=120):
    try:
        r = subprocess.run(['node', MJS, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else None


def article(url, out_png, highlight=None):
    """Mobile screenshot of a news article, scrolled to the highlighted phrase (or the headline). None when a highlight was
    asked for and is not on the page: the shot is then an ad, a paywall or a consent wall, not the article."""
    for _ in range(2):   # page loads and consent pop-ups vary: a miss is tried once more
        res = _run('article', url, str(out_png), *([highlight] if highlight else []))
        if res and (not highlight or res.get('found_highlight')):
            return res['path']
    return None


def card(spec, out_png):
    """Headline card PNG from {outlet, date, headline, quote?}."""
    res = _run('card', json.dumps(spec), str(out_png))
    return res['path'] if res else None
