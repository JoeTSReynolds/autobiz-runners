// One frame, one slider wipe. The `before` actor shows on the left of a divider and the `after` actor on the right
// (same spot, so the divider decides which one you see). The divider teases left and right, then on the `at` word
// it sweeps across with a ring and a burst and reveals the after state, then settles in the middle so both stay
// visible. `beforeLabel` and `afterLabel` (up to 12 chars) are solid tags in the top corners; the after tag pops on
// the sweep. Give no `name` to the actors (the labels do that job). A `result` line lands under the frame.
// Cast anything: a bug and its fix (before asset laptop tint mid "Bug" -> after asset laptop "Fixed"), a surface
// before and after an impact (before image of a plain crater field -> after image of the new crater, labels
// "Before" / "After"), an old chip and the new one (asset chip tint mid -> asset chip), a village and its flood.
(() => {
  const PX = 72, PY = 430, PW = 936, PH = 760, AS = 560;
  BP.define("before-after", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      before: { type: "actor" }, after: { type: "actor" },
      beforeLabel: { type: "text", max: 12 }, afterLabel: { type: "text", max: 12 },
      at: { type: "anchor" }, // the sweep
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const light = p.ground === "light", tag = (cls, side, bg, fg, txt) => `<b class="d ba-tag ${cls}" style="position:absolute;${side}:${96}px;top:${PY + 22}px;height:76px;padding:0 26px;display:flex;align-items:center;font-size:54px;white-space:nowrap;background-color:${bg};color:${fg};opacity:0;z-index:2">${txt}</b>`;
      const layer = (cls, a) => `<div class="${cls}" style="position:absolute;left:${PX}px;top:${PY}px;width:${PW}px;height:${PH}px">${ACT.html({ ...a, name: undefined }, AS, "", PW / 2, PH / 2 + 20)}</div>`;
      return `${p.head ? `<div class="pad d ba-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        <div class="ba-panel" style="position:absolute;left:${PX}px;top:${PY}px;width:${PW}px;height:${PH}px;background-color:currentColor;opacity:0.1"></div>
        ${layer("ba-lb", p.before)}${layer("ba-la", p.after)}
        ${tag("ba-tb", "left", light ? "var(--ink)" : "var(--light)", light ? "var(--light)" : "var(--dark)", p.beforeLabel)}${tag("ba-ta", "right", "var(--accent)", "var(--ink)", p.afterLabel)}
        <div class="ba-div" style="position:absolute;left:${PX}px;top:${PY}px;width:0;height:${PH}px;opacity:0;z-index:1">
          <i style="position:absolute;left:-4px;top:0;width:8px;height:${PH}px;background-color:currentColor"></i>
          <i class="ba-ring" style="position:absolute;left:-60px;top:${PH / 2 - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
          <i style="position:absolute;left:-42px;top:${PH / 2 - 42}px;width:84px;height:84px;border-radius:50%;background-color:var(--accent)"></i>
          <i style="position:absolute;left:-30px;top:${PH / 2 - 14}px;border:14px solid transparent;border-left:0;border-right-color:var(--ink)"></i>
          <i style="position:absolute;left:2px;top:${PH / 2 - 14}px;border:14px solid transparent;border-right:0;border-left-color:var(--ink)"></i>
        </div>
        ${p.result ? `<div class="pad d ba-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 1.6), span = c.end - c.start, st = { x: 0.8 * PW };
      const lb = c.q(".ba-lb"), la = c.q(".ba-la"), dv = c.q(".ba-div");
      let w = 0; // ambient wobble once the wipe is done
      const draw = () => { const x = Math.max(0, Math.min(PW, st.x + w)); lb.style.clipPath = `inset(0 ${PW - x}px 0 0)`; la.style.clipPath = `inset(0 0 0 ${x}px)`; dv.style.left = PX + x + "px"; };
      draw();
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 141, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".ba-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".ba-panel"), { scaleX: 0, transformOrigin: "50% 50%" }, { scaleX: 1, duration: 0.6, ease: "power3.out" }, c.start + 0.05);
      tl.fromTo(c.sel(".ba-div"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4 }, c.start + 0.4);
      tl.fromTo(c.sel(".ba-tb"), { autoAlpha: 0, y: -30 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "back.out(2)" }, c.start + 0.7);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.7, "pop", { step: 1 });
      // the divider teases left and right while it waits
      const d = t - 0.4 - (c.start + 0.9);
      if (d > 1.2) tl.fromTo(st, { x: 0.8 * PW }, { keyframes: [{ x: 0.6 * PW, duration: d / 2, ease: "sine.inOut" }, { x: 0.8 * PW, duration: d / 2, ease: "sine.inOut" }], onUpdate: draw, immediateRender: false }, c.start + 0.9);
      // the wipe, then back to the middle so both show
      tl.fromTo(st, { x: 0.8 * PW }, { x: 0.04 * PW, duration: 0.8, ease: "power3.inOut", onUpdate: draw, immediateRender: false }, t);
      tl.fromTo(st, { x: 0.04 * PW }, { x: 0.5 * PW, duration: 1.3, ease: "power2.inOut", onUpdate: draw, immediateRender: false }, t + 1.1);
      tl.fromTo(c.sel(".ba-ta"), { autoAlpha: 0, scale: 1.6, rotation: -8 }, { autoAlpha: 1, scale: 1, rotation: 0, duration: 0.35, ease: "back.out(2.4)", immediateRender: false }, t + 0.5);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t + 0.75);
      c.particles("burst", t + 0.7, t + 2.4, { at: t + 0.8, x: PX + 0.04 * PW, y: PY + PH / 2, spread: 1.6, dir: 0, g: 200, count: 130, seed: 143, color: c.L.particles.accent });
      c.sfx(t - 0.3, "riser", { dur: 0.3, gain: 0.12 }); c.sfx(t, "whoosh-big", { dur: 0.8, gain: 0.18 }); c.sfx(t + 0.8, "impact", { gain: 0.16 }); c.sfx(t + 0.9, "chime", { step: 3, gain: 0.1 });
      // a ring pings from the handle every 2.4 s: real beats, so the scene never goes still
      for (let u = c.start + 1.2; u < c.end - 0.6; u += 2.4) tl.fromTo(c.sel(".ba-ring"), { scale: 0.3, opacity: 1 }, { scale: 3, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => { const u = c.start + o.t; w = u > t + 2.6 ? Math.sin(u * 1.4) * 12 : 0; draw(); } }, c.start);
      if (p.result) c.rise(".ba-result", p.resultAt ? c.at(p.resultAt) : t + 1.8, { ease: "power4.out" });
    },
  });
})();
