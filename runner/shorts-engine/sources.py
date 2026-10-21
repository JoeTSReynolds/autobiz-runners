#!/usr/bin/env python3
"""Fetch news article pages and save their readable text, one paragraph per line.
Run: python3 sources.py <out-dir> <url> [<url> ...]
Writes <out-dir>/sources.json (id, url, title, published, ok, error, chars, file) and <out-dir>/s1.txt, s2.txt, ...
"""
import json, re, sys, urllib.request
from html import unescape
from html.parser import HTMLParser

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "figure"}
BLOCK = {"p", "h1", "h2", "h3", "li", "blockquote"}
HEADS = {"h1", "h2", "h3"}
MAX_BYTES, MIN_CHARS = 3 * 1024 * 1024, 400


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = self.main = self.block = 0
        self.buf, self.head = [], False
        self.body, self.inmain = [], []   # (text, is_heading) from whole body / from article|main
        self.title, self.og, self.published = "", "", None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = a.get("property") or a.get("name")
            if k == "og:title":
                self.og = a.get("content") or ""
            elif k == "article:published_time":
                self.published = a.get("content")
        elif tag == "title":
            self.in_title = True
        elif tag in SKIP:
            self.skip += 1
        elif tag in ("article", "main"):
            self.main += 1
        elif tag in BLOCK and not self.skip:
            if not self.block:
                self.buf, self.head = [], tag in HEADS
            self.block += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in ("article", "main"):
            self.main = max(0, self.main - 1)
        elif tag in BLOCK and self.block:
            self.block -= 1
            if not self.block:
                t = re.sub(r"\s+", " ", unescape("".join(self.buf))).strip()
                if t:
                    (self.inmain if self.main else self.body).append((t, self.head))

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.block and not self.skip:
            self.buf.append(data)


def extract(html):
    """Return (title, published, paragraphs) from an HTML string."""
    p = Extract()
    p.feed(html)
    chosen = p.inmain or p.body  # shortcut: a page with a tiny <article> hides body text, fine for news
    paras = [t for t, h in chosen if h or len(t) >= 40]
    title = re.sub(r"\s+", " ", unescape(p.title)).strip() or p.og.strip()
    return title, p.published, paras


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:  # follows redirects
        raw = r.read(MAX_BYTES)
        return raw.decode(r.headers.get_content_charset() or "utf-8", "replace")


def main(out, urls):
    import os
    os.makedirs(out, exist_ok=True)
    rows = []
    for i, url in enumerate(urls, 1):
        row = {"id": f"s{i}", "url": url, "title": "", "published": None, "ok": False,
               "error": None, "chars": 0, "file": f"s{i}.txt"}
        try:
            row["title"], row["published"], paras = extract(fetch(url))
            text = "\n".join(paras)
            row["chars"] = len(text)
            open(os.path.join(out, row["file"]), "w", encoding="utf-8").write(text + "\n")
            if row["chars"] < MIN_CHARS:
                row["error"] = f"only {row['chars']} chars extracted (paywall or JavaScript-only?)"
            else:
                row["ok"] = True
        except Exception as e:
            row["error"] = f"{type(e).__name__}: {e}"
        rows.append(row)
        print(f"{row['id']} {'OK  ' if row['ok'] else 'FAIL'} {row['chars']:>6} chars  {row['title'][:60]!r}  {row['error'] or ''}  {url}")
    json.dump(rows, open(os.path.join(out, "sources.json"), "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
