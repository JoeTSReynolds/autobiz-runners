// Big statement lines, each arriving on its own word (default: part start), an optional accent footnote,
// an optional dimmed photo behind, and an optional visual under the lines: "rise-line" (a line climbing
// steeply: only for something that grows or rises over time, like prices or revenue) or "list" (up to
// three short items). The visual always sits below however many lines there are.
BP.define("statement", {
  photo: (p) => !!p.image, // a photo sits behind the caption band
  ground: (p) => p.ground || "dark",
  slots: {
    lines: { type: "list", min: 1, max: 4, of: { text: { type: "text", max: 16 }, at: { type: "anchor", opt: true } } },
    foot: { type: "object", opt: true, of: { text: { type: "text", max: 22 }, at: { type: "anchor" } } },
    image: { type: "image", opt: true }, focus: { type: "point", opt: true },
    visual: { type: "enum", values: ["rise-line", "list"], opt: true },
    visualAt: { type: "anchor", opt: true },
    items: { type: "list", min: 1, max: 3, opt: true, of: { text: { type: "text", max: 14 }, at: { type: "anchor" } } },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html(p) {
    const bare = !p.visual && !p.image; // nothing else on screen: set the lines bigger and centre them
    const size = p.visual ? (p.lines.length > 2 ? 150 : 210) : bare ? 200 : 180;
    const top = p.visual ? 180 : bare ? Math.round(720 - (p.lines.length * size * 0.95 + (p.foot ? 160 : 0)) / 2) : 300;
    const below = Math.round(top + p.lines.length * size * 0.95 + 60); // where a visual can start
    let img = "";
    if (p.image) {
      const m = kit.cover(p.image, 1080, 1920), [fx, fy] = m.px(p.focus || { x: 0.5, y: 0.5 });
      const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(1920 - m.ih, 960 - fy + m.oy));
      img = `<img class="st-img" src="assets/${p.image}" style="position:absolute;left:${x}px;top:${y}px;width:${m.iw}px;height:${m.ih}px;opacity:0.35" />`;
    }
    const vis = p.visual === "rise-line"
      ? `<svg class="pad" style="top:${below}px" width="936" height="${Math.max(260, 1260 - below)}" viewBox="0 0 936 620" preserveAspectRatio="none"><polyline class="st-rise" points="0,600 160,560 300,520 420,430 560,380 680,250 800,170 936,20" fill="none" stroke="var(--accent)" stroke-width="22" stroke-linejoin="miter" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`
      : p.visual === "list"
        ? `<div class="pad" style="top:${Math.max(720, below)}px">${(p.items || []).map((it) => `<div class="t st-item" style="display:flex;align-items:center;gap:28px;font-size:96px;height:140px;opacity:0"><i style="background-color:var(--accent);width:72px;height:72px;display:block;flex:none"></i><span>${it.text}</span></div>`).join("")}</div>` : "";
    return `${img}<div class="pad d st-lines" style="top:${top}px;font-size:${size}px">${p.lines.map((l) => `<div class="line">${l.text}</div>`).join("")}</div>
      ${p.foot ? `<div class="pad d st-foot" style="top:${p.visual === "list" ? Math.max(720, below) + 40 + (p.items || []).length * 140 : p.visual === "rise-line" ? 1290 : bare ? below + 40 : 1000}px;font-size:96px;color:var(--accent-text)"><div class="line">${p.foot.text}</div></div>` : ""}${vis}`;
  },
  animate(c) {
    const { tl, p } = c;
    if (!p.image && !p.visual) c.particles(c.L.particles.ambient, c.start, c.end, { count: 140, seed: 17, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.image) { tl.fromTo(c.sel(".st-img"), { scale: 1.15 }, { scale: 1, duration: c.end - c.start, ease: "none", data: "ambient" }, c.start); c.particles("dust", c.start, c.end, { count: 60, seed: 11, color: c.L.particles.dust }); }
    const ls = c.lines(".st-lines");
    p.lines.forEach((l, i) => {
      const t = l.at ? c.at(l.at) : c.start + 0.05 + i * 0.1;
      tl.fromTo(ls[i], { yPercent: 170 }, { yPercent: 0, duration: 0.6, ease: "expo.out" }, t);
      if (l.at || i === 0) c.sfx(t, "whoosh", { gain: 0.07 });
    });
    if (p.foot) { c.rise(".st-foot", c.at(p.foot.at), { ease: "power4.out" }); c.sfx(c.at(p.foot.at), "blip", { step: 0, dur: 0.6 }); }
    if (p.visual === "rise-line") { const t = c.at(p.visualAt || p.lines[0].at || c.start); tl.to(c.sel(".st-rise"), { attr: { "stroke-dashoffset": 0 }, duration: 1.2, ease: "power2.inOut" }, t); c.sfx(t, "riser", { dur: 1.2, gain: 0.12 }); }
    if (p.visual === "list") c.qa(".st-item").forEach((el, i) => { const t = c.at(p.items[i].at); tl.fromTo(el, { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.5, ease: "expo.out" }, t); c.sfx(t, "pop", { step: 2 + i }); });
  },
});
