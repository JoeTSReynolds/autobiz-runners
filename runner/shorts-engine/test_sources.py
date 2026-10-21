#!/usr/bin/env python3
"""Offline test for sources.extract. Run: python3 test_sources.py"""
from sources import extract

LONG = "The quick brown fox jumps over the lazy dog &amp; keeps running far away."
HTML = f"""<html><head><title> Big   News </title>
<meta property="og:title" content="OG"><meta property="article:published_time" content="2026-10-16T10:00:00Z">
<script>var x = "script text that is long enough to be a paragraph, honestly";</script></head>
<body><nav><p>{LONG} nav</p></nav><p>Outside article paragraph that is long enough to be kept if used.</p>
<article><h2>Short heading</h2><p>{LONG}</p><p>too short</p>
<aside><p>{LONG} aside</p></aside><figure><p>{LONG} figure</p></figure>
<blockquote><p>Quoted words that are definitely longer than forty characters.</p></blockquote>
<ul><li>A list item with more than forty characters in it, yes.</li></ul>
<style>p {{color: red}}</style></article><footer><p>{LONG} footer</p></footer></body></html>"""

title, pub, paras = extract(HTML)
assert title == "Big News", title
assert pub == "2026-10-16T10:00:00Z"
assert paras == ["Short heading",
                 "The quick brown fox jumps over the lazy dog & keeps running far away.",
                 "Quoted words that are definitely longer than forty characters.",
                 "A list item with more than forty characters in it, yes."], paras

# no <article>: falls back to the whole body; og:title used when <title> is missing
t, _, p = extract('<meta property="og:title" content="OG"><body><p>%s</p></body>' % LONG)
assert t == "OG" and len(p) == 1
print("ok")
