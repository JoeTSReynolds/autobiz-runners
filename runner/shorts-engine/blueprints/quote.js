// A pull quote: a big accent quotation mark punches in, then the quote's lines rise one by one, each on its own
// spoken word, and the speaker (`who`) lands under an accent rule on `whoAt`. Optional dimmed `image` behind.
// Use for what a company, agency, official or scientist said: the words must appear word for word in a source page (checked), split
// into lines of up to 20 characters.
BP.define("quote", {
  photo: (p) => !!p.image,
  ground: (p) => p.ground || "dark",
  slots: {
    lines: { type: "list", min: 1, max: 4, of: { text: { type: "text", max: 20 }, at: { type: "anchor" } } },
    who: { type: "text", max: 30 }, whoAt: { type: "anchor" },
    image: { type: "image", opt: true }, focus: { type: "point", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html(p) {
    const n = p.lines.length, size = 130, H = 454 + n * size * 0.95, y0 = Math.round((1400 - H) / 2), ly = y0 + 300; // animate() re-centres once the fit-to-width shrink is known
    let img = "";
    if (p.image) {
      const m = kit.cover(p.image, 1080, 1920), [fx, fy] = m.px(p.focus || { x: 0.5, y: 0.5 });
      const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(1920 - m.ih, 960 - fy + m.oy));
      img = `<img class="qt-img" src="assets/${p.image}" style="position:absolute;left:${x}px;top:${y}px;width:${m.iw}px;height:${m.ih}px;opacity:0.28;filter:grayscale(1)" />`;
    }
    return `${img}<div class="qt-grp"><div class="pad d qt-mark" style="top:${y0 - 125}px;height:300px;font-size:900px;line-height:1;color:var(--accent-text);transform-origin:10% 40%">“</div>
      <div class="pad d qt-lines" style="top:${ly}px;font-size:${size}px">${p.lines.map((l) => `<div class="line">${l.text}</div>`).join("")}</div>
      <i class="qt-rule" style="position:absolute;left:72px;top:${Math.round(ly + n * size * 0.95 + 50)}px;width:170px;height:12px;background-color:var(--accent);transform-origin:left"></i>
      <div class="pad t qt-who" style="font-size:48px;top:${Math.round(ly + n * size * 0.95 + 98)}px"><div class="line">${p.who}</div></div></div>`;
  },
  animate(c) {
    const { tl, p } = c, span = c.end - c.start;
    c.lines(".qt-lines");
    const lh = c.q(".qt-lines").offsetHeight, y0 = Math.round((1400 - (454 - 0.95 * 130 * p.lines.length + lh)) / 2), at = (x, y) => (c.q(x).style.top = y + "px");
    at(".qt-mark", y0 - 125); at(".qt-lines", y0 + 300); at(".qt-rule", y0 + 300 + lh + 50); at(".qt-who", y0 + 300 + lh + 98);
    tl.fromTo(c.sel(".qt-grp"), { y: 0 }, { y: -26, duration: span, ease: "none", data: "ambient" }, c.start);
    if (p.image) tl.fromTo(c.sel(".qt-img"), { scale: 1.12 }, { scale: 1, duration: span, ease: "none", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".qt-mark"), { scale: 2.4, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "power4.out" }, c.start + 0.05);
    c.sfx(c.start + 0.05, "pop", { step: 0, gain: 0.2 });
    p.lines.forEach((l, i) => {
      const t = c.at(l.at);
      c.rise(`.qt-lines .mask:nth-child(${i + 1})`, t, { duration: 0.7 });
      c.sfx(t, "blip", { step: i + 1, gain: 0.08 });
    });
    const w = c.at(p.whoAt);
    tl.fromTo(c.sel(".qt-rule"), { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "expo.out" }, w);
    c.rise(".qt-who", w + 0.15);
    c.sfx(w, "click", { f0: 1200 }); c.sfx(w + 0.2, "chime", { step: 2, gain: 0.06 });
  },
});
