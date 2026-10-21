// A 10 x 10 grid of 100 squares; on `at` the first `filled` squares flip to the accent colour in reading order
// with a fast ticking stagger, then a big `figure` ("80%", "8 in 10") rises above the grid and an optional short
// `label` under it. Use for shares and proportions: "8 in 10 people", "a third of the budget", "41%".
BP.define("dot-grid", {
  ground: "dark",
  slots: {
    at: { type: "anchor" },
    filled: { type: "number", min: 1, max: 100 },
    figure: { type: "text", max: 8 },
    label: { type: "text", max: 26, opt: true }, labelAt: { type: "anchor", opt: true },
  },
  html(p) {
    const top = p.label ? 470 : 400;
    return `<div class="pad d dg-fig" style="top:100px;font-size:270px"><div class="line">${p.figure}</div></div>
      ${p.label ? `<div class="pad t dg-lab" style="top:375px"><div class="line">${p.label}</div></div>` : ""}
      <div class="dg-wrap" style="position:absolute;left:72px;top:${top}px;width:936px;height:936px;transform-origin:50% 0"><div class="dg-grid" style="display:grid;grid-template-columns:repeat(10,72px);gap:24px">
        ${"<i style='display:block;width:72px;height:72px;background-color:var(--light);opacity:0.16'></i>".repeat(100)}</div></div>`;
  },
  animate(c) {
    const { tl, p } = c, t = c.at(p.at), cells = [...c.qa(".dg-grid i")].slice(0, Math.floor(p.filled)), step = Math.min(0.04, Math.max(0.012, 1.5 / cells.length));
    tl.fromTo(c.sel(".dg-wrap"), { scale: 1 }, { scale: 1.03, duration: c.end - c.start, ease: "none", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".dg-grid"), { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.55, ease: "expo.out" }, c.start);
    c.sfx(c.start, "whoosh", { gain: 0.08 });
    tl.to(cells, { scaleX: 0, duration: 0.05, ease: "power1.in", stagger: step }, t);
    tl.to(cells, { backgroundColor: c.L.colors.accent, opacity: 1, duration: 0.001, stagger: step }, t + 0.05);
    tl.to(cells, { scaleX: 1, duration: 0.1, ease: "back.out(3)", stagger: step }, t + 0.05);
    const ticks = 14, span = (cells.length - 1) * step;
    for (let k = 0; k < ticks; k++) c.sfx(t + (k * span) / (ticks - 1), "click", { f0: 1400 + k * 180, gain: 0.07 });
    const done = t + span + 0.15;
    c.rise(".dg-fig", done, { duration: 0.7, ease: "power4.out" });
    c.sfx(done, "pop", { step: 5 }); c.sfx(done + 0.05, "whoosh", { gain: 0.07 });
    if (p.label) c.rise(".dg-lab", p.labelAt ? c.at(p.labelAt) : done + 0.5);
  },
});
