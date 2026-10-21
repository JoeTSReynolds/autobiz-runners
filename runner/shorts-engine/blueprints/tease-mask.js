// Open loop: an ink panel slides up over the scene and glitches, with a line of text and a masked number
// ("??¢") that scrambles through symbols and pulses until the scene ends. Resolve it later with a reveal blueprint.
BP.define("tease-mask", {
  overlay: true,
  covers: 0.5, // the panel fills the frame 0.5 s after it starts
  ground: "dark",
  slots: {
    lines: { type: "lines", max: 26, lines: 2 }, textAt: { type: "anchor" }, pulseAt: { type: "anchor" },
    unit: { type: "text", max: 2, opt: true },
  },
  html: (p) => `<div class="tm" style="position:absolute;inset:0;background-color:var(--dark)">
    <div class="pad t tm-txt" style="top:300px;color:var(--light);font-size:64px">${p.lines.map((l) => `<div class="line">${l}</div>`).join("")}</div>
    <div class="pad d tm-num" style="top:560px;font-size:560px;color:var(--accent-text)">??${p.unit || "¢"}</div></div>`,
  animate(c) {
    const { tl, p } = c, unit = p.unit || "¢", t = c.at(p.textAt), t0 = t + 0.2, dur = c.sceneEnd - t0, node = c.q(".tm-num"), o = { p: 0 };
    tl.fromTo(c.sel(".tm"), { yPercent: 100 }, { yPercent: 0, duration: 0.45, ease: "expo.out" }, c.start);
    tl.to(c.sel(".tm"), { keyframes: [-30, 22, -12, 0].map((x) => ({ x, duration: 0.05, ease: "steps(1)" })) }, c.start + 0.45);
    c.sfx(c.start, "whoosh-big", { dur: 0.5 });
    c.rise(".tm-txt", t);
    // scrambles through symbols, 12 steps a second: never digits, so no paused frame shows a made-up figure
    tl.to(o, { p: 1, duration: dur, ease: "none", onUpdate: () => { const k = Math.floor(o.p * dur * 12); node.textContent = ["??", "?#", "%?", "?!", "#?"][k % 5] + unit; } }, t0);
    for (let s = 0; s < dur; s += 0.5) c.sfx(t0 + s, "click", { f0: 2200, gain: 0.04 });
    tl.fromTo(node, { scale: 0.85 }, { scale: 1.1, duration: 0.25, yoyo: true, repeat: 3, ease: "power2.inOut" }, c.at(p.pulseAt));
  },
});
