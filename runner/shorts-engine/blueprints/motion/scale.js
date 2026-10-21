// A size comparison. The `subject` grows in alone at close zoom with its size label counting up (`subjectSize`,
// e.g. "27 km"); on the `at` word the `reference` grows in beside it and the camera eases out to the true relative
// sizes, a ruler draws under each with its own label (`referenceSize`), and a line like "about 20× bigger" lands (left out under 1.5×)
// (override it with `result`). `ratio` is how many times the subject is bigger than the reference: 20 means 20x
// bigger, 0.1 means a tenth the size; true scale holds from 0.05 to 20 (the smaller one is found with a pulse ring).
// Cast anything: Phobos (asset moon, 22 km) against London (label "London" or a photo, 50 km, ratio 0.44); a
// transistor chip against a hair; the Moon against Earth (ratio 0.27); a data centre against a football pitch.
const SC = { base: 1180, gap: 60, W: 936 };
SC.auto = (p) => { const R = Math.max(p.ratio, 1 / p.ratio); return p.result || (R < 1.5 ? "" : `about ${Math.round(R)}× ${p.ratio >= 1 ? "bigger" : "smaller"}`); };
SC.nm = (a) => (a.name && a.name.toLowerCase() !== (a.label || "").toLowerCase() ? a.name : ""); // a label actor already says its own name
SC.sizes = (p) => { // the bigger actor fills up to 700 px; true relative sizes beyond that
  const R = Math.max(p.ratio, 1 / p.ratio), big = Math.min(700, (SC.W - SC.gap) / (1 + 1 / R)), s = p.ratio >= 1 ? big : big / R, r = p.ratio >= 1 ? big / R : big, x0 = 540 - (s + r + SC.gap) / 2;
  return { s, r, x0, x1: x0 + s + SC.gap };
};
BP.define("scale", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    subject: { type: "actor" }, reference: { type: "actor" }, ratio: { type: "number", min: 0.05, max: 20 },
    subjectSize: { type: "text", max: 14, opt: true }, referenceSize: { type: "text", max: 14, opt: true },
    at: { type: "anchor" }, // the reference arrives
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html(p) {
    const a = SC.sizes(p), lab = (i, t, cls) => `<div class="d sc-lab sc-lab${i}" style="position:absolute;left:0;top:0;width:520px;text-align:center;font-size:76px;opacity:0;${cls}"><span>${t || ""}</span></div>`;
    const nm = (i, a) => `<div class="t sc-name sc-name${i}" style="position:absolute;left:0;top:0;width:520px;text-align:center;opacity:0;white-space:nowrap;color:var(--af, currentColor)">${SC.nm(a)}</div>`;
    const rule = (i, col) => `<div class="sc-rule sc-rule${i}" style="position:absolute;left:0;top:0;height:30px;color:${col}"><div class="sc-ri" style="position:absolute;inset:0;opacity:0"><i style="position:absolute;left:0;top:0;width:6px;height:30px;background:currentColor"></i><i style="position:absolute;right:0;top:0;width:6px;height:30px;background:currentColor"></i><i style="position:absolute;left:0;right:0;top:12px;height:6px;background:currentColor"></i></div></div>`;
    return `${p.head ? `<div class="pad d sc-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      <div class="sc-ground" style="position:absolute;left:72px;right:72px;height:6px;top:0;background-color:var(--mid);opacity:0"></div>
      <div class="sc-g" style="position:absolute;left:0;top:0;width:0;height:0;transform-origin:0 0">
        ${ACT.html({ ...p.subject, name: undefined }, a.s, "sc-a0", a.x0 + a.s / 2, SC.base - a.s / 2)}${ACT.html({ ...p.reference, name: undefined }, a.r, "sc-a1", a.x1 + a.r / 2, SC.base - a.r / 2)}</div>
      ${nm(0, p.subject)}${nm(1, p.reference)}${rule(0, "var(--accent)")}${rule(1, "currentColor")}${lab(0, p.subjectSize, "color:var(--accent-text)")}${lab(1, p.referenceSize, "")}
      <div class="sc-ping" style="position:absolute;border-radius:50%;border:12px solid var(--accent);opacity:0"></div>
      ${SC.auto(p) ? `<div class="pad d sc-result" style="top:372px;font-size:100px;color:var(--accent-text);z-index:2"><div class="line">${SC.auto(p)}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, a = SC.sizes(p), tS = c.start + 0.1, tR = Math.max(c.at(p.at), c.start + 1.4), small = a.s < a.r ? 0 : 1;
    const cx = [a.x0 + a.s / 2, a.x1 + a.r / 2], sz = [a.s, a.r], cyc = [SC.base - a.s / 2, SC.base - a.r / 2];
    const Z0 = Math.min(16, Math.max(1, 340 / a.s)), D = 1.2, ease = (k) => (k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2);
    const cam = (t) => { // close on the subject, then pull out to the whole picture
      const Zs = Z0 * (1 + 0.04 * Math.min(1, Math.max(0, (t - tS) / (tR - tS)))), Ts = [540 - Zs * cx[0], 800 - Zs * cyc[0]], k = ease(Math.min(1, Math.max(0, (t - tR) / D)));
      return { Z: Zs ** (1 - k), x: Ts[0] * (1 - k), y: Ts[1] * (1 - k) };
    };
    const G = c.q(".sc-g"), el = (s) => c.q(s), at = (e, x, y) => Object.assign(e.style, { left: x + "px", top: y + "px" });
    const frame = (t) => {
      const { Z, x, y } = cam(t), by = y + Z * SC.base;
      G.style.transform = `translate(${x}px,${y}px) scale(${Z})`; at(el(".sc-ground"), 72, by);
      [0, 1].forEach((i) => {
        const X = x + Z * cx[i], r0 = x + Z * (cx[i] - sz[i] / 2), w = Z * sz[i], low = i !== small || a.s === a.r;
        at(el(`.sc-name${i}`), X - 260, low ? by + 12 : y + Z * (SC.base - sz[i]) - 64);
        Object.assign(el(`.sc-rule${i}`).style, { left: r0 + "px", width: w + "px", top: by + (low ? 84 : 72) + "px" });
        at(el(`.sc-lab${i}`), X - 260, by + (low ? 120 : 108));
      });
    };
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 12, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".sc-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    const o = { t: 0 };
    tl.to(o, { t: c.end - c.start, duration: c.end - c.start, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
    const grow = (i, t) => {
      tl.fromTo(c.sel(`.sc-a${i}`), { scale: 0, autoAlpha: 0, transformOrigin: "50% 100%" }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.6)" }, t);
      tl.fromTo(c.sel(".sc-ground"), { opacity: 0 }, { opacity: 1, duration: 0.4, immediateRender: false }, Math.min(t, tS));
      tl.fromTo(c.sel(`.sc-name${i}`), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4 }, t + 0.3);
      tl.fromTo(c.sel(`.sc-rule${i} .sc-ri`), { scaleX: 0, opacity: 1, transformOrigin: "50% 50%" }, { scaleX: 1, duration: 0.7, ease: "power3.out", immediateRender: false }, t + 0.6);
      tl.set(c.sel(`.sc-lab${i}`), { opacity: 1 }, t + 0.7);
      c.sfx(t, "pop", { step: i * 2 }); c.sfx(t + 0.6, "whoosh", { dur: 0.5, gain: 0.07 });
      const txt = [p.subjectSize, p.referenceSize][i], m = txt && txt.match(/^([\d,]*\.?\d+)(.*)$/);
      if (m) { const dec = (m[1].split(".")[1] || "").length; c.count(`.sc-lab${i} span`, 0, parseFloat(m[1].replace(/,/g, "")), t + 0.7, 1.1, (v) => (m[1].includes(",") ? v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : v.toFixed(dec)) + m[2]); }
    };
    grow(0, tS); c.sfx(tS, "whoosh", { gain: 0.08 });
    c.sfx(tR - 0.2, "riser", { dur: D + 1.2, gain: 0.14 });
    const tG = tR + D - 0.2;
    grow(1, tG);
    const tH = tG + 1.0, px = a.x0 + (small ? a.s + SC.gap : 0) + sz[small] / 2, ping = Math.min(260, Math.max(80, sz[small] * 1.4));
    Object.assign(c.q(".sc-ping").style, { left: px - ping / 2 + "px", top: SC.base - sz[small] / 2 - ping / 2 + "px", width: ping + "px", height: ping + "px" });
    tl.fromTo(c.sel(".sc-ping"), { scale: 0.6, opacity: 1 }, { scale: 1.8, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, tH);
    tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-10, 6], [8, -6], [-4, 3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tH);
    c.particles("burst", tH - 0.05, tH + 1.7, { at: tH, x: px, y: SC.base - sz[small] / 2, spread: 3.1, g: 100, count: 90, seed: 71, color: c.L.particles.accent });
    c.sfx(tH, "impact", { gain: 0.16 }); c.sfx(tH + 0.05, "chime", { step: 3, gain: 0.09 });
    if (SC.auto(p)) c.rise(".sc-result", p.resultAt ? c.at(p.resultAt) : tH + 0.2, { ease: "power4.out" });
  },
});
