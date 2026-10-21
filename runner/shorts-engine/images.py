# One interface over free-licence image sources: NASA, Wikimedia Commons, Openverse, Pexels, Pixabay.
#   python3 images.py search "<query>" [n]                  -> JSON list (providers interleaved in priority order)
#   python3 images.py get <project> <provider> "<title>" <name.jpg>
#       re-runs search(title, 20) (cached 24 h), picks the result with that provider+title (or page URL).
#       Fragile for NASA titles; pipelines should call get(project, result, name) with the result dict.
#      
#       downloads it to <project>/assets/<name>, appends the credit to <project>/credits.json.
# Licence rule (allowed()): public domain, CC0, CC BY, CC BY-SA, Pexels, Pixabay. Never NC / ND.
# PEXELS_API_KEY / PIXABAY_API_KEY enable those providers. Keys go only in request URL/headers; the cache
# stores normalised results (no keys) and failed providers are recorded in last_errors.
import hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

import commons

UA = {"User-Agent": "newsroom-media/1.0"}  # Pixabay 403s the default Python UA
CACHE = Path("~/.cache/autobiz-images").expanduser()
OK = ("public domain", "pd", "cc0", "cc by", "cc-by", "pexels license", "pixabay content license", "no restrictions")
MIN_W = 1000  # drop results known to be narrower; unknown size (NASA) passes
last_errors = []


def allowed(lic):
    lic = (lic or "").lower()
    return lic.startswith(OK) and not re.search(r"\b(nc|nd)\b", lic)  # "cc by-sa" has no standalone nd/nc


def fetch(url, headers=None, timeout=30):
    h = {**(commons.UA if "wikimedia" in url else UA), **(headers or {})}
    for attempt in range(4):  # back off on 429 like commons.py
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 5 * (attempt + 1)))


def jget(url, headers=None):
    return json.loads(fetch(url, headers))


def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def item(provider, title, page, lic, artist, w, h, desc, thumb):
    return {"provider": provider, "title": title, "page": page, "license": lic, "artist": strip(artist)[:80],
            "width": w, "height": h, "description": strip(desc)[:200], "thumb": thumb}


# ---- providers: each returns normalised, licence-filtered dicts ---------------------------------

def nasa_items(d, manifest):  # manifest(url) -> list of asset URLs
    out = []
    for it in d.get("collection", {}).get("items", []):
        m = (it.get("data") or [{}])[0]
        text = " ".join([m.get("description") or "", m.get("description_508") or "", *(m.get("keywords") or [])]).lower()
        who = m.get("photographer") or m.get("secondary_creator") or ""
        if "courtesy of" in text or (who and "nasa" not in who.lower()):
            continue  # other organisation / non-NASA photographer: rights not NASA's to waive
        urls = manifest(it["href"]) if it.get("href") else []
        pick = next((u for suf in ("~orig.jpg", "~large.jpg") for u in urls if u.lower().endswith(suf)), None)
        if pick:
            out.append(item("nasa", m.get("title", ""), "https://images.nasa.gov/details/" + m.get("nasa_id", ""),
                            "Public domain (NASA)", who or "NASA", None, None, m.get("description", ""), pick.replace(" ", "%20")))
    return out


def nasa(q, n):
    d = jget("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "image"}))
    d["collection"]["items"] = d["collection"]["items"][:n]
    return nasa_items(d, lambda u: jget(u))


OV_LIC = {"cc0": "CC0", "pdm": "Public domain", "by": "CC BY", "by-sa": "CC BY-SA"}


def openverse_items(d):
    out = []
    for r in d.get("results", []):
        if r.get("license") in OV_LIC:  # drops by-nc, by-nd etc.
            lic = f"{OV_LIC[r['license']]} {r.get('license_version') or ''}".strip()
            out.append(item("openverse", r.get("title") or "", r.get("foreign_landing_url"), lic, r.get("creator") or "",
                            r.get("width"), r.get("height"), ", ".join(t["name"] for t in r.get("tags") or []), r.get("url")))
    return out


def openverse(q, n):
    return openverse_items(jget("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {"q": q, "license_type": "commercial,modification", "page_size": n})))


def pexels_items(d):
    return [item("pexels", p.get("alt") or f"Pexels {p['id']}", p["url"], "Pexels License", p.get("photographer", ""),
                 p.get("width"), p.get("height"), p.get("alt", ""), p["src"]["large2x"]) for p in d.get("photos", [])]


def pexels(q, n):
    return pexels_items(jget("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": n}),
                             {"Authorization": os.environ["PEXELS_API_KEY"]}))


def pixabay_items(d):
    return [item("pixabay", f"Pixabay {h['id']}: {h.get('tags', '')}", h["pageURL"], "Pixabay Content License", h.get("user", ""),
                 h.get("imageWidth"), h.get("imageHeight"), h.get("tags", ""), h["largeImageURL"]) for h in d.get("hits", [])]


def pixabay(q, n):
    return pixabay_items(jget("https://pixabay.com/api/?" + urllib.parse.urlencode(
        {"key": os.environ["PIXABAY_API_KEY"], "q": q, "image_type": "photo", "per_page": max(3, n)})))


def commons_search(q, n):
    return [{**r, "provider": "commons", "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(r["title"].replace(" ", "_"))}
            for r in commons.search(q, n)]


PROVIDERS = [("nasa", nasa, None), ("commons", commons_search, None), ("openverse", openverse, None),
             ("pexels", pexels, "PEXELS_API_KEY"), ("pixabay", pixabay, "PIXABAY_API_KEY")]


def cached(cache_dir, name, q, n, fn):
    f = Path(cache_dir) / (name + "-" + hashlib.sha1(f"{q}|{n}".encode()).hexdigest()[:16] + ".json")
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        return json.loads(f.read_text())
    res = fn(q, n)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(res))
    return res


def search(query, n=8, cache_dir=None):
    cache_dir = cache_dir or CACHE
    per = []
    for name, fn, env in PROVIDERS:
        if env and not os.environ.get(env):
            continue
        try:
            rs = cached(cache_dir, name, query, n, fn)
            per.append([r for r in rs if allowed(r["license"]) and (r["width"] or MIN_W) >= MIN_W])
        except Exception as e:  # one provider failing must not fail the search
            last_errors.append(f"{name}: {type(e).__name__}: {str(e)[:150]}")
    # interleave so n=4 gives a mix, not four NASA hits; priority order is kept within each round
    merged = [r for round_ in zip(*[p + [None] * (n - len(p)) for p in per]) for r in round_ if r]
    return merged[:n]


def get(project, result, name):
    dest = Path(project) / "assets" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name("dl-" + name)
    tmp.write_bytes(fetch(result["thumb"], timeout=60))
    # always re-encode: providers serve WebP/PNG under any name, and a real JPEG keeps ffprobe and Chrome in agreement
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-frames:v", "1", "-vf", "scale='min(2400,iw)':-2", "-q:v", "2", dest], check=True)
    tmp.unlink()
    credits = Path(project) / "credits.json"
    c = json.loads(credits.read_text()) if credits.exists() else {}
    c[name] = {k: result[k] for k in ("title", "license", "artist", "provider", "page")}
    credits.write_text(json.dumps(c, indent=1, ensure_ascii=False))
    print(f"{name}: {result['title']} ({result['license']}, {result['artist']}, {result['provider']})")


if __name__ == "__main__":
    if sys.argv[1] == "search":
        print(json.dumps(search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8), indent=1, ensure_ascii=False))
    elif sys.argv[1] == "get":
        project, provider, title, name = sys.argv[2:6]
        hit = next((r for r in search(re.sub(r'[^\w ]+', ' ', title), 20) if r["provider"] == provider and title in (r["title"], r["page"])), None)
        hit or sys.exit(f"{provider}: {title!r} not found in search results (use the exact title or page URL)")
        get(project, hit, name)
    for e in last_errors:
        print("provider error:", e, file=sys.stderr)
