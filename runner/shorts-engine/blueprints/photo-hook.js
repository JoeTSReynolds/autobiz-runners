// Hook: a real photo on top with data sparks, then an accent block slams up carrying a lead-in, a counting
// number and a closing line. Captions go to the accent ground when the block lands. Follow it with a
// tease overlay; the hook ends (sparks stop, readings end) where that overlay starts.
BP.define("photo-hook", {
  ground: "dark",
  slots: {
    image: { type: "image" }, focus: { type: "point", opt: true }, // focus = image point centred in the photo
    lead: { type: "lines", max: 36, lines: 2 }, slamAt: { type: "anchor" },
    num: { type: "object", of: {
      to: { type: "number", min: 0, max: 999 }, at: { type: "anchor" }, pulseAt: { type: "anchor", opt: true },
      prefix: { type: "text", max: 2, opt: true }, suffix: { type: "text", max: 2, opt: true },
    } },
    when: { type: "object", of: { text: { type: "text", max: 16 }, at: { type: "anchor" } } },
  },
  html(p) {
    const m = kit.cover(p.image, 1080, 700), [fx, fy] = m.px(p.focus || { x: 0.5, y: 0.5 });
    const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(700 - m.ih, 350 - fy + m.oy));
    return `<div class="ph-photo" style="position:absolute;left:0;top:0;width:1080px;height:700px;background:url(assets/${p.image}) ${x}px ${y}px/${m.iw}px ${m.ih}px no-repeat;filter:grayscale(1) contrast(1.3) brightness(0.95)"></div>
    <div class="ph-block" style="position:absolute;left:0;right:0;top:640px;height:1280px;background-color:var(--accent);color:var(--ink)">
      <div class="pad t ph-lead" style="top:64px">${p.lead.map((l) => `<div class="line">${l}</div>`).join("")}</div>
      <div class="pad d ph-num" style="top:250px;font-size:330px">${p.num.prefix || ""}0${p.num.suffix || ""}</div>
      <div class="pad d ph-when" style="top:570px;font-size:150px"><div class="line">${p.when.text}</div></div>
    </div>`;
  },
  animate(c) {
    const { tl, p } = c, n = p.num, slam = c.at(p.slamAt), end = c.next, dec = (String(n.to).split(".")[1] || "").length;
    c.particles("sparks", c.start, end, { count: 40, seed: 2, color: c.L.particles.accent });
    tl.fromTo(c.sel(".ph-photo"), { scale: 1.12 }, { scale: 1, duration: c.sceneEnd - c.start, ease: "none", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".ph-block"), { yPercent: 100 }, { yPercent: 0, duration: 0.55, ease: "expo.out" }, slam);
    c.sfx(slam, "whoosh", { dur: 0.4, f0: 200, f1: 1800, gain: 0.18 });
    c.ground(slam, "accent");
    c.rise(".ph-lead", slam + 0.15, { until: end });
    c.count(".ph-num", 0, n.to, c.at(n.at), 1.3, (v) => (n.prefix || "") + v.toFixed(dec) + (n.suffix || ""));
    if (n.pulseAt) tl.fromTo(c.sel(".ph-num"), { scale: 1 }, { scale: 1.08, duration: 0.15, yoyo: true, repeat: 1, transformOrigin: "left center" }, c.at(n.pulseAt));
    c.rise(".ph-when", c.at(p.when.at), { ease: "back.out(1.4)", until: end });
    tl.set(c.sel(".ph-block"), { visibility: "hidden" }, end + 0.45); // the overlay has covered it by now
  },
});
