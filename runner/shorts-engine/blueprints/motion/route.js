// A `traveller` actor moves along a winding dashed path that turns accent behind it. 2..4 dated `stops`
// ({text up to 14 chars, at}) are spaced evenly along the way and the traveller reaches each one exactly on its
// word: a pin drops in with a ring and a burst and a solid tag with the stop's text snaps in beside it. The last
// stop is the end of the path. Keep stops in spoken order. Afterwards the end pin keeps pinging. A `result` line
// lands under the route.
// Cast anything: a product roadmap (traveller asset rocket or label "Roadmap"; stops "Q1 Beta", "Q3 Launch",
// "2027 Scale"), mission milestones to 2031 (traveller asset satellite; stops "2026 Launch", "2029 Flyby",
// "2031 Arrival"), a parcel's journey (asset packet; stops "Packed", "Shipped", "Delivered"), a career path.
(() => {
  const D = "M180 1200C180 1050 880 1100 860 930S200 840 240 720S760 640 880 540", TZ = 260;
  BP.define("route", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      traveller: { type: "actor" },
      stops: { type: "list", min: 2, max: 4, of: { text: { type: "text", max: 14 }, at: { type: "anchor" } } },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      return `${p.head ? `<div class="pad d rt-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        <svg style="position:absolute;left:0;top:0;overflow:visible" width="1080" height="1920"><path class="rt-base" d="${D}" fill="none" stroke="var(--mid)" stroke-width="10" stroke-linecap="round" stroke-dasharray="2 26" opacity="0"/><path class="rt-run" d="${D}" fill="none" stroke="var(--accent)" stroke-width="14" stroke-linecap="round" pathLength="1" stroke-dasharray="1 2" stroke-dashoffset="1"/></svg>
        ${p.stops.map((s, i) => `<div class="rt-s rt-s${i}" style="position:absolute;left:0;top:0;z-index:1">
          <i class="rt-ring" style="position:absolute;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
          <i class="rt-dot" style="position:absolute;width:52px;height:52px;border-radius:50%;background-color:var(--accent);border:10px solid var(--ink);box-sizing:border-box"></i>
          <b class="d rt-tag" style="position:absolute;height:76px;padding:0 24px;display:flex;align-items:center;white-space:nowrap;font-size:52px;background-color:var(--accent);color:var(--ink)">${s.text}</b></div>`).join("")}
        ${ACT.html({ ...p.traveller, name: undefined }, TZ, "rt-trav", TZ / 2, TZ / 2)}
        ${p.result ? `<div class="pad d rt-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, n = p.stops.length, span = c.end - c.start, path = c.q(".rt-run"), len = path.getTotalLength();
      const stops = p.stops.map((s, i) => ({ ...s, i, t: c.at(s.at), f: (i + 1) / n })).sort((a, b) => a.t - b.t).map((s, k) => ({ ...s, f: (k + 1) / n }));
      const pt = (f) => { const q = path.getPointAtLength(Math.min(1, Math.max(0, f)) * len); return [q.x, q.y]; };
      const tS = Math.max(c.start + 0.3, Math.min(c.start + 1.0, stops[0].t - 0.9)), trav = c.q(".rt-trav"), tv = c.q(".rt-trav .act-v"), st = { f: 0 };
      let bob = 0;
      const draw = () => { const [x, y] = pt(st.f); Object.assign(trav.style, { left: x - TZ / 2 + "px", top: y - TZ / 2 + bob + "px" }); path.setAttribute("stroke-dashoffset", 1 - st.f); };
      stops.forEach((s) => { // each pin sits on the path; its tag goes to the side with more room
        const [x, y] = pt(s.f), g = c.q(`.rt-s${s.i}`), tag = g.querySelector(".rt-tag"), w = tag.offsetWidth, left = x > 540;
        const tx = Math.max(24, Math.min(1056 - w, left ? x - 50 - w : x + 50));
        g.querySelector(".rt-ring").style.cssText += `;left:${x - 60}px;top:${y - 60}px`; g.querySelector(".rt-dot").style.cssText += `;left:${x - 26}px;top:${y - 26}px`;
        tag.style.left = tx + "px"; tag.style.top = y - 38 + "px"; tag.dataset.side = left ? "r" : "l";
        s.x = x; s.y = y;
      });
      draw();
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 151, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".rt-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".rt-base"), { opacity: 0 }, { opacity: 0.9, duration: 0.6 }, c.start + 0.1);
      tl.fromTo(c.sel(".rt-trav"), { scale: 0.4, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.7)" }, c.start + 0.3);
      c.sfx(c.start + 0.3, "whoosh", { gain: 0.08 });
      // the journey: one tween, easing into each stop so the traveller is on the pin on its word
      let prev = tS;
      const kf = stops.map((s) => { const d = Math.max(0.5, s.t - prev); prev = s.t; return { f: s.f, duration: d, ease: "power2.inOut" }; });
      tl.fromTo(st, { f: 0 }, { keyframes: kf, onUpdate: draw, immediateRender: false }, tS);
      c.sfx(tS, "riser", { dur: stops.at(-1).t - tS, gain: 0.1 });
      stops.forEach((s, k) => {
        tl.fromTo(c.sel(`.rt-s${s.i} .rt-dot`), { scale: 0 }, { scale: 1, duration: 0.45, ease: "back.out(3)", transformOrigin: "50% 50%", immediateRender: false }, s.t);
        tl.set(c.sel(`.rt-s${s.i} .rt-dot`), { scale: 0 }, 0);
        tl.fromTo(c.sel(`.rt-s${s.i} .rt-ring`), { scale: 0.3, opacity: 1 }, { scale: 3.5, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, s.t);
        const side = c.q(`.rt-s${s.i} .rt-tag`).dataset.side;
        tl.fromTo(c.sel(`.rt-s${s.i} .rt-tag`), { clipPath: side === "r" ? "inset(0% 0% 0% 100%)" : "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.35, ease: "power3.out", immediateRender: false }, s.t + 0.1);
        tl.set(c.sel(`.rt-s${s.i} .rt-tag`), { clipPath: side === "r" ? "inset(0% 0% 0% 100%)" : "inset(0% 100% 0% 0%)" }, 0);
        tl.fromTo(c.sel(".rt-trav"), { scale: 1 }, { scale: 1.14, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, s.t);
        c.particles("burst", s.t - 0.05, s.t + 1.5, { at: s.t, x: s.x, y: s.y, spread: 3.1, g: 200, count: 60, seed: 153 + k, color: c.L.particles.accent });
        c.sfx(s.t, "blip", { step: k + 1, dur: 0.3 }); c.sfx(s.t + 0.1, "click", { f0: 2400, gain: 0.08 });
      });
      const tL = stops.at(-1).t;
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-12, 6], [10, -6], [-6, 3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tL);
      c.sfx(tL, "impact", { gain: 0.14 }); c.sfx(tL + 0.1, "chime", { step: 3, gain: 0.1 });
      // after the last stop the end pin keeps pinging (real beats)
      for (let u = tL + 1.2; u < c.end - 0.5; u += 2.4) tl.fromTo(c.sel(`.rt-s${stops.at(-1).i} .rt-ring`), { scale: 0.3, opacity: 1 }, { scale: 3.5, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => { bob = Math.sin((c.start + o.t) * 4) * 7; draw(); tv.style.transform = `rotate(${Math.sin((c.start + o.t) * 2.2) * 4}deg)`; } }, c.start);
      if (p.result) c.rise(".rt-result", p.resultAt ? c.at(p.resultAt) : tL + 1.0, { ease: "power4.out" });
    },
  });
})();
