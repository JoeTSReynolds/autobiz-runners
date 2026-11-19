import sys, json, subprocess
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("headline-card.py needs Pillow (point AUTOBIZ_PYTHON at a venv with it)")

rows, family, size, emoji, out = json.loads(sys.argv[1]), sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
S, MAX = 4, 1000  # supersampling for smooth corners; widest card in px
font_file = subprocess.run(["fc-match", "-f", "%{file}", family + ":bold"], capture_output=True, text=True).stdout.strip()
if not font_file:
    sys.exit("fc-match found no bold font for " + family)
pic = Image.open(emoji).convert("RGBA") if emoji else None

def layout(size):
    font = ImageFont.truetype(font_file, round(size * S))
    asc, desc = font.getmetrics()
    emoji_h = round(1.05 * size * S)
    emoji_w = round(pic.width * emoji_h / pic.height) if pic else 0
    widths = []
    for i, row in enumerate(rows):
        w = font.getlength(row) + 2 * 0.32 * size * S
        if pic and i == len(rows) - 1:
            w += 0.15 * size * S + emoji_w
        widths.append(w)
    return font, asc, desc, emoji_h, emoji_w, widths

while True:
    font, asc, desc, emoji_h, emoji_w, widths = layout(size)
    if max(widths) <= MAX * S:
        break
    size *= 0.97

pad_y, overlap = round(0.16 * size * S), round(0.12 * size * S)
box_h = asc + desc + 2 * pad_y
width, height = round(max(widths)), box_h * len(rows) - overlap * (len(rows) - 1)
img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
for i, row in enumerate(rows):
    top = i * (box_h - overlap)
    left = (width - widths[i]) / 2
    draw.rounded_rectangle([left, top, left + widths[i], top + box_h], radius=round(0.28 * size * S), fill=(255, 255, 255, 255))
    x = left + 0.32 * size * S
    draw.text((x, top + pad_y + asc), row, font=font, fill=(0, 0, 0, 255), anchor="ls")
    if pic and i == len(rows) - 1:
        small = pic.resize((emoji_w, emoji_h), Image.LANCZOS)
        img.alpha_composite(small, (round(x + font.getlength(row) + 0.15 * size * S), top + (box_h - emoji_h) // 2))
width, height = round(width / S), round(height / S)
img.resize((width, height), Image.LANCZOS).save(out)
print(json.dumps({"width": width, "height": height}))
