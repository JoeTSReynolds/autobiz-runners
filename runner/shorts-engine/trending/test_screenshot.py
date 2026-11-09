# screenshot.mjs on local pages (no network): article with highlight, card, wrapper returns path or None.
# Needs Node and Playwright's Chromium; prints "skip" when Chromium cannot start. Run: python3 test_screenshot.py
import json, struct, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import screenshot

def png_size(p): return struct.unpack('>II', Path(p).read_bytes()[16:24])

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    page = d / 'a.html'
    page.write_text('<html><head><title>Hi</title></head><body><div style="position:fixed;top:0">COOKIES</div>'
                    '<h1>Headline</h1>' + '<p>filler text</p>' * 80 + '<p>the quick brown fox jumps</p>' + '<p>more</p>' * 80 + '</body></html>')
    out = d / 'a.png'
    r = subprocess.run(['node', str(Path(screenshot.__file__).with_name('screenshot.mjs')), 'article', page.as_uri(), str(out), 'quick brown fox'],
                       capture_output=True, text=True)
    if r.returncode and 'xecutable' in r.stderr:
        print('skip: no chromium'); sys.exit(0)
    assert r.returncode == 0, r.stderr[-400:]
    res = json.loads(r.stdout.strip().splitlines()[-1])
    assert res['found_highlight'] is True and res['title'] == 'Hi', res
    assert png_size(out) == (1075, 1910), png_size(out)  # 430 css px * 2.5 wide, 9:16 high (764 css px)
    assert screenshot.article(page.as_uri(), str(d / 'b.png')) == str(d / 'b.png')
    assert screenshot.card({'outlet': 'BBC', 'date': '5 Nov', 'headline': 'Big <news>', 'quote': 'said so'}, str(d / 'c.png')) == str(d / 'c.png')
    assert png_size(d / 'c.png')[0] == 1000, png_size(d / 'c.png')
    assert screenshot.article('file:///nonexistent/x.html', str(d / 'z.png')) is None
    # a highlight that is not on the page means the shot is not the article (live 2026-11-07: an NBC page rendered as a
    # 'Coolest 23+ Gifts' ad box): refused, so assets tries the next screenshot
    assert screenshot.article(page.as_uri(), str(d / 'h.png'), 'words that are not there') is None
    assert screenshot.article(page.as_uri(), str(d / 'g.png'), 'quick brown fox') == str(d / 'g.png')
print('ok')
