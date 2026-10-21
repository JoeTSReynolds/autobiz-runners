// The hero reveal (tech): a masked number scrambles until the word, then locks onto the real one with a
// riser and impact; a dollar becomes the wafer, its dies light up to that number and burst, then closing lines.
BP.define("wafer-reveal", {
  ground: "dark",
  slots: {
    to: { type: "number", min: 1, max: 99 }, heroAt: { type: "anchor" },
    lead: { type: "lines", max: 16, lines: 2 },
    bill: { type: "object", of: { text: { type: "text", max: 4 }, at: { type: "anchor" }, waferAt: { type: "anchor" } } }, // bill shows at `at`, turns into the wafer at `waferAt`
    pureAt: { type: "anchor" },
    close: { type: "object", of: { lines: { type: "lines", max: 30, lines: 2 }, at: { type: "anchor" }, emphasisAt: { type: "anchor" } } },
  },
  html: (p) => `<div class="pad d wv-num" style="top:130px;font-size:180px;color:var(--accent-text)">??¢</div>
    <div class="pad t wv-lead" style="top:150px;left:420px">${p.lead.map((l) => `<div class="line">${l}</div>`).join("")}</div>
    <div class="pad d wv-bill" style="top:560px;font-size:600px;text-align:center;color:var(--light)">${p.bill.text}</div>
    <div class="pad t wv-close" style="top:1190px;font-size:60px">${p.close.lines.map((l) => `<div class="line">${l}</div>`).join("")}</div>
    <svg class="wv-wafer" viewBox="-450 -450 900 900" style="position:absolute;left:90px;top:330px;width:900px;height:900px;visibility:hidden"></svg>`,
  animate(c) {
    const { tl, p } = c, C = c.L.colors, hero = c.at(p.heroAt), sil = c.at(p.bill.waferAt), svg = c.sel(".wv-wafer");
    const wafer = c.L.drawWafer(c.q(".wv-wafer"), 440, 68, 8), lit = wafer.dies.slice(0, p.to), node = c.q(".wv-num"), o = { p: 0 }, dur = hero - c.start;
    tl.to(o, { p: 1, duration: dur, ease: "none", onUpdate: () => { const k = Math.floor(o.p * dur * 12); node.textContent = (k % 5 === 0 ? "??" : String(((k * 37 + 11) % 89) + 10)) + "¢"; } }, c.start);
    for (let s = 0; s < dur; s += 0.5) c.sfx(c.start + s, "click", { f0: 2200, gain: 0.04 });
    c.rise(".wv-lead", hero + 0.3, { stagger: 0.12 });
    tl.fromTo(c.sel(".wv-bill"), { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(2)" }, c.at(p.bill.at));
    tl.to(c.sel(".wv-bill"), { opacity: 0, scale: 0.2, duration: 0.4, ease: "power3.in" }, sil);
    c.sfx(c.at(p.bill.at), "pop", { step: 2 });
    tl.set(svg, { visibility: "visible" }, sil);
    tl.fromTo(svg, { y: 120, rotation: -40, scale: 0.1 }, { y: 120, rotation: 0, scale: 1, duration: 0.8, ease: "expo.out", immediateRender: false }, sil);
    c.hero(hero);
    c.count(".wv-num", p.to - 14, p.to, hero, 0.5, (v) => Math.round(v) + "¢"); // the scramble locks onto the real number
    tl.to(lit, { attr: { fill: C.accent }, duration: 0.05, stagger: 0.012, ease: "none" }, hero);
    tl.fromTo(svg, { scale: 1 }, { scale: 1.06, duration: 0.12, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, hero);
    c.particles("burst", hero, hero + 1.8, { at: hero, x: 540, y: 900, count: 140, seed: 31, color: c.L.particles.accent, spread: 2.2, g: 600 });
    tl.to(lit, { attr: { fill: "#ff7a3d" }, duration: 0.12, yoyo: true, repeat: 1 }, c.at(p.pureAt));
    const cl = c.at(p.close.at);
    tl.to(svg, { y: 20, scale: 0.75, duration: 0.8, ease: "power3.inOut" }, cl);
    c.rise(".wv-close", cl + 0.2);
    tl.fromTo(c.sel(".wv-close .line"), { color: C.light }, { color: C.accent, duration: 0.2 }, c.at(p.close.emphasisAt));
  },
});
