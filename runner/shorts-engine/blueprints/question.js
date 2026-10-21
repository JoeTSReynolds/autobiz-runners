// A big question built line by line, each line arriving on its own word, the tail lines in the accent
// colour, over an optional dim photo that pans slowly. `focus` = the image point centred on screen.
BP.define("question", {
  photo: (p) => !!p.image, // a photo sits behind the caption band
  ground: "dark",
  slots: {
    lines: { type: "list", min: 2, max: 6, of: { text: { type: "text", max: 14 }, at: { type: "anchor", opt: true } } },
    accentFrom: { type: "number", min: 0, max: 5, opt: true },
    image: { type: "image", opt: true }, focus: { type: "point", opt: true },
    shake: { type: "bool", opt: true },
  },
  html(p) {
    let img = "";
    if (p.image) {
      const m = kit.cover(p.image, 1080, 1920), [fx, fy] = m.px(p.focus || { x: 0.5, y: 0.5 });
      const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(1920 - m.ih, 960 - fy + m.oy));
      img = `<img class="q-img" src="assets/${p.image}" style="position:absolute;left:${x}px;top:${y}px;width:${m.iw}px;height:${m.ih}px;opacity:0.22;filter:grayscale(1)" />`;
    }
    return `${img}<div class="pad d q-lines" style="top:260px;font-size:168px">${p.lines.map((l, i) => `<div class="line"${i >= (p.accentFrom ?? 99) ? ' style="color:var(--accent-text)"' : ""}>${l.text}</div>`).join("")}</div>`;
  },
  animate(c) {
    const { tl, p } = c, ls = c.lines(".q-lines");
    if (p.image) tl.fromTo(c.sel(".q-img"), { x: 0 }, { x: -220, duration: c.end - c.start, ease: "none", data: "ambient" }, c.start);
    let last = 0;
    p.lines.forEach((l, i) => {
      last = l.at ? c.at(l.at) : c.start + 0.05;
      tl.fromTo(ls[i], { yPercent: 170 }, { yPercent: 0, duration: 0.5, ease: "expo.out" }, last);
      c.sfx(last, "blip", { step: i, gain: 0.08 });
    });
    if (p.shake) tl.fromTo(c.sel(".q-lines"), { x: 0 }, { x: 8, duration: 0.04, repeat: 5, yoyo: true, ease: "none" }, last + 0.25);
  },
});
