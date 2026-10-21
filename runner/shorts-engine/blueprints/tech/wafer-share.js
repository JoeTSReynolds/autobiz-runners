// Share chart on a wafer (tech): a dark board fades in over the previous part (a chip dive), a wafer spins
// in, and each group lights its share of the 100 dies on its word, with a legend row and a big figure.
// After a chip-dive, the dive's zoom ends at this part's start; the board lands 0.2 s later.
const WS_COL = (C) => ({ accent: C.accent, tint: C.tint, white: "#ffffff", mid: C.mid });
BP.define("wafer-share", {
  overlay: true,
  covers: 0.5, // the dark board is fully in 0.45 s after the part starts
  ground: "dark",
  slots: {
    head: { type: "text", max: 24 },
    groups: { type: "list", min: 2, max: 4, of: { // dies are handed out in list order: each group's pct = its dies
      label: { type: "text", max: 20 }, pct: { type: "number", min: 1, max: 99 }, color: { type: "enum", values: ["accent", "tint", "white", "mid"] },
      at: { type: "anchor" }, pulseAt: { type: "anchor", opt: true }, dim: { type: "bool", opt: true }, // dim: "the rest", lands just after its word
    } },
    big: { type: "object", of: { text: { type: "text", max: 5 }, at: { type: "anchor" } } },
  },
  html(p) {
    const C = WS_COL(LANE.colors);
    return `<div class="ws" style="position:absolute;inset:0;background-color:var(--dark);opacity:0">
      <div class="pad t ws-head" style="top:130px;color:var(--light)"><div class="line">${p.head}</div></div>
      <div class="pad ws-legend" style="top:1040px;color:var(--light)">${p.groups.map((g) => `<div class="t ws-row" style="display:flex;align-items:center;gap:28px;font-size:60px;height:86px;${g.dim ? "color:var(--mid)" : ""}"><i style="width:52px;height:52px;display:block;flex:none;background-color:${C[g.color]}"></i><span>${g.label}</span><span style="margin-left:auto">${g.pct}%</span></div>`).join("")}</div>
      <div class="pad d ws-big" style="top:200px;font-size:250px;color:var(--accent-text);text-align:right"><div class="line">${p.big.text}</div></div></div>
    <svg class="ws-wafer" viewBox="-450 -450 900 900" style="position:absolute;left:90px;top:330px;width:900px;height:900px;visibility:hidden"></svg>`;
  },
  animate(c) {
    const { tl, p } = c, C = WS_COL(c.L.colors), t0 = c.start + 0.2, svg = c.sel(".ws-wafer"), wafer = c.L.drawWafer(c.q(".ws-wafer"), 440, 68, 8);
    c.ground(t0, "dark");
    tl.fromTo(c.sel(".ws"), { opacity: 0 }, { opacity: 1, duration: 0.25 }, t0);
    tl.set(svg, { visibility: "visible" }, t0);
    tl.fromTo(svg, { scale: 2.4, rotation: -30, y: -150 }, { scale: 0.6, rotation: 0, y: -150, duration: 0.9, ease: "expo.out", immediateRender: false }, t0);
    c.rise(".ws-head", t0 + 0.1);
    tl.fromTo(c.sel(".ws-row"), { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.5, ease: "expo.out", stagger: 0.12 }, c.at(p.groups[0].at));
    let k = 0;
    p.groups.forEach((g, i) => {
      const dies = wafer.dies.slice(k, (k += g.pct)), t = c.at(g.at) + (g.dim ? 0.4 : 0);
      tl.to(dies, { attr: { fill: C[g.color] }, duration: 0.05, stagger: Math.min(0.06, 0.5 / g.pct) }, t); // each group lights over ~0.5 s
      if (g.pulseAt) tl.to(dies, { attr: { fill: C.accent }, duration: 0.15, yoyo: true, repeat: 3 }, c.at(g.pulseAt));
      if (!g.dim) c.sfx(g.pulseAt ? c.at(g.pulseAt) : t, "blip", { step: i * 2 });
    });
    c.rise(".ws-big", c.at(p.big.at), { ease: "power4.out" });
    c.sfx(c.at(p.big.at), "pop", { step: 4 });
  },
});
