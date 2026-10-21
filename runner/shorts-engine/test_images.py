# Offline tests for images.py: licence filter + per-provider normalisation. Run: python3 test_images.py
import images as I

for ok in ("Public domain (NASA)", "CC0", "CC BY 4.0", "CC BY-SA 3.0", "Pexels License", "Pixabay Content License", "Public domain"):
    assert I.allowed(ok), ok
for bad in ("CC BY-NC 4.0", "CC BY-ND 2.0", "CC BY-NC-SA 2.0", "All rights reserved", "", None):
    assert not I.allowed(bad), bad

# NASA: courtesy-of and non-NASA photographer are skipped; ~orig preferred over ~large; size unknown
def man(u):
    return ["http://x/a~thumb.jpg", "http://x/a~large.jpg", "http://x/a~orig.jpg", "http://x/a~orig.tif"]
mk = lambda **m: {"href": "http://m", "data": [{"nasa_id": "A1", "title": "T", "description": "d", **m}]}
r = I.nasa_items({"collection": {"items": [
    mk(), mk(description="Image courtesy of ESA"), mk(keywords=["Courtesy of Getty"]), mk(photographer="Jane Doe"),
    mk(photographer="NASA/JPL-Caltech")]}}, man)
assert [x["artist"] for x in r] == ["NASA", "NASA/JPL-Caltech"], r
assert r[0]["thumb"].endswith("~orig.jpg") and r[0]["width"] is None and r[0]["license"] == "Public domain (NASA)"
assert I.nasa_items({"collection": {"items": [mk()]}}, lambda u: ["http://x/a~large.jpg"])[0]["thumb"].endswith("~large.jpg")
assert I.nasa_items({"collection": {"items": [mk()]}}, lambda u: ["http://x/a.tif"]) == []

# Openverse: only cc0/pdm/by/by-sa
ov = {"results": [{"license": l, "license_version": "4.0", "title": l, "foreign_landing_url": "p", "url": "u", "creator": "C",
                   "width": 3000, "height": 2000, "tags": [{"name": "moon"}]} for l in ("cc0", "pdm", "by", "by-sa", "by-nc", "by-nd", "by-nc-sa")]}
r = I.openverse_items(ov)
assert [x["title"] for x in r] == ["cc0", "pdm", "by", "by-sa"] and all(I.allowed(x["license"]) for x in r), r
assert r[2]["license"] == "CC BY 4.0" and r[0]["description"] == "moon" and r[0]["provider"] == "openverse"

# Pexels / Pixabay
r = I.pexels_items({"photos": [{"id": 1, "url": "pg", "photographer": "Ann", "width": 4000, "height": 3000, "alt": "a moon",
                                "src": {"large2x": "big"}}]})[0]
assert (r["license"], r["artist"], r["thumb"], r["page"], r["title"]) == ("Pexels License", "Ann", "big", "pg", "a moon")
r = I.pixabay_items({"hits": [{"id": 9, "pageURL": "pg", "tags": "moon, sky", "user": "Bob", "imageWidth": 5000, "imageHeight": 3000,
                               "largeImageURL": "big"}]})[0]
assert (r["license"], r["artist"], r["thumb"], r["width"]) == ("Pixabay Content License", "Bob", "big", 5000)
assert "key" not in str(r).lower()

# search(): failing provider is recorded, others survive, size filter keeps unknown width, cache avoids refetch
import tempfile
calls = []
def good(q, n): calls.append(q); return [{"provider": "g", "license": "CC0", "width": None}, {"provider": "g", "license": "CC0", "width": 300},
                                         {"provider": "g", "license": "CC BY-NC 2.0", "width": 3000}]
def bad(q, n): raise RuntimeError("boom")
I.PROVIDERS[:] = [("good", good, None), ("bad", bad, None)]
d = tempfile.mkdtemp()
assert len(I.search("q", 5, cache_dir=d)) == 1 and len(I.search("q", 5, cache_dir=d)) == 1
assert len(calls) == 1 and len(I.last_errors) == 2 and "boom" in I.last_errors[0]
print("all tests passed")

# get: a provider serving WebP (rawpixel via Openverse) still lands as a real JPEG, so ffprobe/Chrome see what the name says
import subprocess, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
    webp = Path(d) / "src.webp"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=640x360", "-frames:v", "1", webp], check=True)
    I.fetch = lambda url, timeout=60: webp.read_bytes()
    I.get(d, {"thumb": "u", "title": "t", "license": "CC0", "artist": "a", "provider": "openverse", "page": "p"}, "c1.jpg")
    assert (Path(d) / "assets" / "c1.jpg").read_bytes()[:2] == b"\xff\xd8", "not a JPEG"
print("images tests ok")
