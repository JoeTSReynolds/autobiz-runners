// Years down the page, each arriving on its word; optional photo "snap" with radar rings, a suspected-void
// outline and a zoom, all on their words. A row with count:true counts up from the previous row's year.
BP.define("timeline-years", {
  ground: "light",
  slots: {
    rows: { type: "list", min: 2, max: 4, of: {
      year: { type: "text", max: 6 }, text: { type: "text", max: 60 }, at: { type: "anchor" },
      count: { type: "bool", opt: true }, accent: { type: "bool", opt: true },
    } },
    emphasis: { type: "object", opt: true, of: { row: { type: "number", min: 0, max: 3 }, at: { type: "anchor" } } },
    snap: { type: "object", opt: true, of: {
      image: { type: "image" }, focus: { type: "point" }, at: { type: "anchor" },
      ringsAt: { type: "anchor", opt: true }, voidAt: { type: "anchor", opt: true }, zoomAt: { type: "anchor", opt: true },
    } },
  },
  html(p) {
    let snap = "";
    if (p.snap) {
      const m = kit.cover(p.snap.image, 800, 800), [fx, fy] = m.px(p.snap.focus);
      snap = `<div class="ty-snap" style="position:absolute;left:600px;top:980px;width:408px;height:408px;border:8px solid var(--ink);overflow:hidden;background-color:var(--ink)">
        <img class="ty-img" src="assets/${p.snap.image}" style="position:absolute;left:${196 - fx + m.ox}px;top:${196 - fy + m.oy}px;width:${m.iw}px;height:${m.ih}px" />
        <svg style="position:absolute;left:0;top:0" width="392" height="392">${[0, 1, 2].map(() => `<circle class="ty-ring" cx="196" cy="196" r="40" fill="none" stroke="var(--accent)" stroke-width="5" opacity="0"/>`).join("")}
          <ellipse class="ty-void" cx="196" cy="300" rx="170" ry="46" fill="none" stroke="var(--accent)" stroke-width="5" stroke-dasharray="16 10" opacity="0"/></svg>
        <div class="ty-flash" style="position:absolute;inset:0;background-color:#fff;opacity:0"></div></div>`;
    }
    return `<div class="pad" style="top:200px">${p.rows.map((r, i) => `<div class="ty-row" style="display:flex;gap:40px;align-items:baseline;margin-bottom:70px;${r.accent ? "color:var(--accent-text)" : ""}">
      <div class="d ty-year" style="font-size:170px;width:420px;flex:none">${r.year}</div><div class="t ty-text" style="font-size:46px">${r.text}</div></div>`).join("")}</div>${snap}`;
  },
  animate(c) {
    const { tl, p } = c, rows = c.qa(".ty-row");
    p.rows.forEach((r, i) => {
      const t = c.at(r.at);
      tl.fromTo(rows[i], { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.6, ease: "expo.out" }, t);
      c.sfx(t, "pop", { step: i * 2 });
      if (r.count && i > 0 && /^\d+$/.test(p.rows[i - 1].year) && /^\d+$/.test(r.year)) {
        const node = rows[i].querySelector(".ty-year"), o = { v: +p.rows[i - 1].year };
        tl.fromTo(o, { v: +p.rows[i - 1].year }, { v: +r.year, duration: 0.7, ease: "power3.out", onUpdate: () => (node.textContent = String(Math.round(o.v))) }, t);
      }
    });
    if (p.emphasis) {
      const t = c.at(p.emphasis.at), row = rows[p.emphasis.row];
      tl.to(row.querySelector(".ty-text"), { color: c.L.colors.accent, duration: 0.2 }, t);
      tl.fromTo(row, { scale: 1 }, { scale: 1.04, duration: 0.25, yoyo: true, repeat: 1, transformOrigin: "left center" }, t);
    }
    if (p.snap) {
      const s = p.snap, t = c.at(s.at);
      tl.fromTo(c.sel(".ty-snap"), { opacity: 0, rotation: -6, scale: 0.8 }, { opacity: 1, rotation: 2, scale: 1, duration: 0.5, ease: "back.out(2)" }, t);
      tl.fromTo(c.sel(".ty-flash"), { opacity: 0.9 }, { opacity: 0, duration: 0.4 }, t);
      c.sfx(t, "click", { f0: 2400, gain: 0.18 });
      if (s.ringsAt) { const r = c.at(s.ringsAt); tl.fromTo(c.sel(".ty-ring"), { attr: { r: 40 }, opacity: 0.9 }, { attr: { r: 190 }, opacity: 0, duration: 1.0, stagger: 0.25, ease: "power1.out" }, r); c.sfx(r, "blip", { step: 1 }); c.sfx(r + 0.5, "blip", { step: 2 }); }
      if (s.voidAt) tl.to(c.sel(".ty-void"), { opacity: 1, duration: 0.4 }, c.at(s.voidAt));
      if (s.zoomAt) tl.to(c.sel(".ty-img"), { scale: 1.12, duration: 0.6, ease: "power2.out" }, c.at(s.zoomAt));
    }
  },
});
