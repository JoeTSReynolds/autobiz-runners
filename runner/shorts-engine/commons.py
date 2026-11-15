# Wikimedia Commons image search + download with a licence whitelist and credit capture.
#   python3 commons.py search "<query>" [n]           -> JSON list of usable files
#   python3 commons.py get <project> "<File:Title>" <name.jpg>  -> downloads to <project>/assets/<name.jpg>,
#                                                                appends the credit to <project>/credits.json
import json, re, sys, urllib.parse
from pathlib import Path
from shared import web

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "autobiz-newsroom/0.1 (non-commercial prototype; python-urllib)"}
OK = ("public domain", "pd", "cc0", "cc by", "cc-by", "no restrictions")  # cc by-sa included via "cc by"


def fetch(url, timeout=30):
    return web.fetch(url, UA, timeout)  # Commons rate-limits bursts (429): fetch waits and retries


def api(**q):
    return json.loads(fetch(API + "?" + urllib.parse.urlencode({"format": "json", **q})))


def info(pages):
    out = []
    for p in pages.values():
        i = (p.get("imageinfo") or [{}])[0]
        m = i.get("extmetadata", {})
        lic = m.get("LicenseShortName", {}).get("value", "")
        if not any(lic.lower().startswith(o) for o in OK) or re.search(r"\b(nc|nd)\b", lic.lower()):
            continue  # only free licences; never non-commercial or no-derivatives
        if i.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        artist = re.sub(r"<[^>]+>", "", m.get("Artist", {}).get("value", "")).strip()
        out.append({"title": p["title"], "license": lic, "artist": artist[:80], "width": i.get("width"), "height": i.get("height"),
                    "description": re.sub(r"<[^>]+>", "", m.get("ImageDescription", {}).get("value", ""))[:200],
                    "thumb": i.get("thumburl")})
    return out


def search(query, n=12):
    d = api(action="query", generator="search", gsrnamespace=6, gsrlimit=n, gsrsearch=query, prop="imageinfo",
            iiprop="url|size|mime|extmetadata", iiurlwidth=2000, iiextmetadatafilter="LicenseShortName|Artist|ImageDescription")
    return info(d.get("query", {}).get("pages", {}))


def get(project, title, name):
    d = api(action="query", titles=title, prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=2000,
            iiextmetadatafilter="LicenseShortName|Artist|ImageDescription")
    files = info(d["query"]["pages"])
    if not files:
        sys.exit(f"{title}: not found or not freely licensed")
    f, dest = files[0], Path(project) / "assets" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(fetch(f["thumb"], 60))
    credits = Path(project) / "credits.json"
    c = json.loads(credits.read_text()) if credits.exists() else {}
    c[name] = {k: f[k] for k in ("title", "license", "artist")}
    credits.write_text(json.dumps(c, indent=1, ensure_ascii=False))
    print(f"{name}: {f['title']} ({f['license']}, {f['artist']})")


if __name__ == "__main__":
    if sys.argv[1] == "search":
        print(json.dumps(search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12), indent=1, ensure_ascii=False))
    elif sys.argv[1] == "get":
        get(*sys.argv[2:5])
