// Two halves stacked, top and bottom: a before/after or a claim/reality. Each half has a solid accent `label`
// tag and a big `text`, and may have its own `image` (otherwise the top half is dark, the bottom light). The top
// half shows at the start; the bottom half slides in on `b.at` behind an accent divider that wipes across.
// Use for comparisons that are not numbers: then vs now, promised vs delivered, what they said vs what happened.
const SP_HALF = { label: { type: "text", max: 14 }, text: { type: "text", max: 18 }, image: { type: "image", opt: true }, focus: { type: "point", opt: true } };
const spHalf = (h, k, y0, y1) => { // y0..y1 = the half's band; text sits bottom-left of it, label top-left
  let img = "";
  if (h.image) {
    const m = kit.cover(h.image, 1080, y1 - y0), [fx, fy] = m.px(h.focus || { x: 0.5, y: 0.5 });
    const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(y1 - y0 - m.ih, (y1 - y0) / 2 - fy + m.oy));
    img = `<div style="position:absolute;inset:0;overflow:hidden"><img class="sp-img-${k}" src="assets/${h.image}" style="position:absolute;left:${x}px;top:${y}px;width:${m.iw}px;height:${m.ih}px" /></div><i style="position:absolute;inset:0;background-color:rgba(11,11,11,0.55)"></i>`;
  }
  const dark = k === "a" || h.image, fg = dark ? "var(--light)" : "var(--ink)", bg = h.image ? "var(--dark)" : dark ? "var(--dark)" : "var(--light)";
  return `<div class="sp-${k}" style="position:absolute;left:0;top:${y0}px;width:1080px;height:${y1 - y0}px;overflow:hidden;background-color:${bg};color:${fg}">${img}
    <div class="sp-blk-${k}" style="position:absolute;left:72px;width:936px;bottom:${k === "a" ? 860 : 520}px;display:flex;flex-direction:column;align-items:flex-start;gap:28px">
      <div class="lbl sp-tag-${k}" style="padding:14px 28px;background-color:var(--accent);color:var(--ink);font-size:46px;clip-path:inset(0 100% 0 0)">${h.label}</div>
      <div class="d sp-txt-${k}" data-fitw="936" style="font-size:250px;white-space:nowrap;color:${fg}"><div class="line">${h.text}</div></div></div></div>`; // the tag sits on its text, so a shrunk line never leaves it stranded
};
BP.define("split", {
  photo: (p) => !!(p.a.image || p.b.image),
  ground: "dark",
  slots: {
    a: { type: "object", of: SP_HALF },
    b: { type: "object", of: { ...SP_HALF, at: { type: "anchor" } } },
  },
  html: (p) => spHalf(p.a, "a", 0, 1920) + `<div class="sp-bwrap" style="position:absolute;inset:0">${spHalf(p.b, "b", 860, 1920)}</div><i class="sp-div" style="position:absolute;left:0;top:846px;width:1080px;height:28px;background-color:var(--accent);transform-origin:left"></i>`,
  animate(c) {
    const { tl, p } = c, t = c.at(p.b.at), span = c.end - c.start;
    tl.fromTo(c.sel(".sp-tag-a"), { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.45, ease: "expo.out" }, c.start + 0.1);
    c.rise(".sp-txt-a", c.start + 0.2, { duration: 0.7 });
    c.sfx(c.start + 0.1, "pop", { step: 0 });
    tl.fromTo(c.sel(".sp-a"), { clipPath: "inset(0px 0px 0px 0px)" }, { clipPath: "inset(0px 0px 1060px 0px)", duration: 0.6, ease: "expo.out", immediateRender: false }, t + 0.1); // the top half starts full-frame, then makes room
    tl.fromTo(c.sel(".sp-txt-a"), { x: 0 }, { x: -24, duration: span, ease: "none", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".sp-blk-a"), { y: 0 }, { y: -260, duration: 0.6, ease: "expo.out", immediateRender: false }, t + 0.1);
    if (!p.a.image) c.particles(c.L.particles.ambient, c.start, t + 0.7, { count: 100, seed: 41, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    for (const k of ["a", "b"]) if (p[k].image) tl.fromTo(c.sel(".sp-img-" + k), { scale: 1.12 }, { scale: 1, duration: span, ease: "none", data: "ambient" }, c.start);
    c.ground(t, p.b.image ? "dark" : "light");
    tl.fromTo(c.sel(".sp-div"), { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: "expo.out" }, t - 0.05);
    tl.fromTo(c.sel(".sp-bwrap"), { y: 1060 }, { y: 0, duration: 0.6, ease: "expo.out" }, t + 0.1);
    tl.fromTo(c.sel(".sp-tag-b"), { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.45, ease: "expo.out" }, t + 0.4);
    c.rise(".sp-txt-b", t + 0.5, { duration: 0.7 });
    c.sfx(t - 0.05, "click", { f0: 1000 }); c.sfx(t + 0.1, "whoosh-big", { dur: 0.5, gain: 0.2 }); c.sfx(t + 0.45, "pop", { step: 3 });
  },
});
