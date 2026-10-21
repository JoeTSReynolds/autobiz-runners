// Copies of an `item` actor drop one by one into a growing wall (or a narrow tower), landing with a bounce and a
// puff of dust, faster and faster, while a big running `count` ticks up with them. The count reaches `total`
// exactly on the `at` word, where the whole stack pops with a shake and a burst. `unit` follows the number
// ("blocks", "tonnes"); `shape` is wall (default, wide, up to 36 copies drawn) or tower (two columns, up to 14).
// Cast anything: 100 hidden text blocks in a page (asset document, unit "blocks"), tonnes of samples (asset rock,
// unit "tonnes"), servers in a data centre (asset server, tower), coins in a treasury (asset coin).
BP.define("stack", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    item: { type: "actor" }, total: { type: "number", min: 2, max: 999999999 }, unit: { type: "text", max: 12, opt: true },
    at: { type: "anchor" }, // the count lands on its total
    shape: { type: "enum", values: ["wall", "tower"], opt: true },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html(p) {
    const g = STK.geo(p);
    return `${p.head ? `<div class="pad d st-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      <div class="pad d st-count" style="top:${g.ct}px;font-size:150px;white-space:nowrap"><span class="st-n" style="color:var(--accent-text)">0</span><span class="st-u" style="font-size:72px;margin-left:24px">${p.unit || ""}</span></div>
      <div class="st-floor" style="position:absolute;left:72px;right:72px;top:${g.floor}px;height:6px;background-color:var(--mid);opacity:0"></div>
      <div class="st-g" style="position:absolute;left:0;top:0">${Array.from({ length: g.M }, (_, k) => ACT.html({ ...p.item, name: undefined }, g.size, `st-i st-i${k}`, g.x(k), g.y(k))).join("")}</div>
      ${p.result ? `<div class="pad d st-result" style="top:1318px;font-size:96px;color:var(--accent-text)"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, g = STK.geo(p), tS = c.start + 1.0, tA = Math.max(c.at(p.at), tS + 1.8), M = g.M, n = (v) => v.toLocaleString("en-US");
    const land = (k) => tS + (tA - tS) * (M > 1 ? (k / (M - 1)) ** 0.6 : 0), cv = kit.canvas("#" + c.box.id).getContext("2d");
    const nEl = c.q(".st-n"), stride = Math.ceil(M / 22);
    const frame = (t) => { // the count and the dust puffs are pure functions of time
      let landed = 0; cv.clearRect(0, 0, 1080, 1920);
      for (let k = 0; k < M; k++) {
        const age = t - land(k); if (age < 0) continue; landed++;
        if (age > 0.55) continue;
        for (let j = 0; j < 5; j++) { const d = (j % 2 ? 1 : -1) * (14 + 38 * (j + 1) * age + ((k * 7 + j * 3) % 9)), up = 24 * age - 70 * age * age;
          cv.globalAlpha = 0.7 * (1 - age / 0.55); cv.fillStyle = `rgb(${c.L.particles.dust})`; cv.fillRect(g.x(k) + d * 0.7, g.y(k) + g.size / 2 - 6 - up, 7 - j, 7 - j); }
      }
      nEl.textContent = n(landed >= M ? p.total : Math.round((p.total * landed) / M));
    };
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 15, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".st-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    tl.fromTo(c.sel(".st-count"), { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: "power3.out" }, c.start + 0.15);
    tl.fromTo(c.sel(".st-floor"), { opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, duration: 0.7, ease: "power3.out" }, c.start + 0.3);
    c.sfx(c.start + 0.15, "whoosh", { gain: 0.08 });
    const o = { t: 0 };
    tl.to(o, { t: c.end - c.start, duration: c.end - c.start, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
    for (let k = 0; k < M; k++) {
      const t = land(k) - 0.55;
      tl.fromTo(c.sel(`.st-i${k}`), { y: -Math.max(40, Math.min(420, g.y(k) - g.ct - 170 - g.size / 2)), autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.55, ease: "bounce.out", immediateRender: true }, t);
      tl.fromTo(c.sel(`.st-i${k} .act-v`), { scaleY: 1.18, scaleX: 0.9, transformOrigin: "50% 100%" }, { scaleY: 1, scaleX: 1, duration: 0.3, ease: "back.out(2)", immediateRender: false }, land(k));
      if (k % stride === 0) c.sfx(land(k), "pop", { step: k % 5, dur: 0.1, gain: 0.07 });
    }
    c.sfx(tS - 0.5, "riser", { dur: tA - tS + 0.5, gain: 0.1 });
    tl.fromTo(c.sel(".st-g"), { scale: 1, transformOrigin: `540px ${g.floor}px` }, { scale: 1.06, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tA + 0.05);
    tl.fromTo(c.sel(".st-count"), { scale: 1, transformOrigin: "0 50%" }, { scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tA + 0.05);
    tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-12, 8], [10, -8], [-6, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tA + 0.05);
    c.particles("burst", tA, tA + 1.7, { at: tA + 0.05, x: 540, y: g.top, spread: 1.4, g: 700, count: 120, seed: 77, color: c.L.particles.accent });
    c.sfx(tA + 0.05, "impact", { gain: 0.16 }); c.sfx(tA + 0.1, "chime", { step: 3, gain: 0.1 });
    if (p.result) c.rise(".st-result", p.resultAt ? c.at(p.resultAt) : tA + 0.5, { ease: "power4.out" });
  },
});
const STK = {
  geo(p) { // grid of M copies on the floor, the column count chosen for the biggest copies; rows alternate by half a copy
    const tower = p.shape === "tower", M = Math.min(p.total, tower ? 14 : 36), floor = p.result ? 1290 : 1370, ct = p.head ? 370 : 320, top = ct + 190, H = floor - top - 10;
    let cols = tower ? 2 : 3, best = 0;
    if (!tower) for (let k = 3; k <= 10; k++) { const sz = Math.min(900 / (k + 0.5), H / Math.ceil(M / k)); if (sz > best) { best = sz; cols = k; } }
    const rows = Math.ceil(M / cols), size = Math.floor(Math.min(900 / (cols + 0.5), H / rows) * 0.94), W = size * cols + size / 2;
    return { M, cols, rows, size, ct, top: floor - rows * size, floor, x: (k) => 540 - W / 2 + size / 2 + (k % cols) * size + (Math.floor(k / cols) % 2 ? size / 2 : 0), y: (k) => floor - size / 2 - Math.floor(k / cols) * size };
  },
};
