// A `whole` actor trembles, an accent crack runs through it and on the `at` word it breaks: shards and debris
// fly, a shockwave ring and flash go off, and 2..3 labelled `parts` (each an actor with its own `name`) fly out
// of it and drift apart, bobbing, for the rest of the scene. Give every part a `name`. A `result` line lands under.
// Cast anything: a company spun off into units (whole asset building named "MegaCorp"; parts: asset cloud
// "Cloud", asset chip "Chips"), a comet breaking apart (whole asset comet; parts asset rock x3, tint mid),
// a mission splitting into probes (whole asset satellite -> asset lander + asset rocket), a platform unbundled
// (whole asset server -> label "Search" + label "Maps").
(() => {
  const W = [540, 810, 560], SLOTS = { 2: { s: 330, at: [[270, 720], [810, 920]] }, 3: { s: 270, at: [[250, 640], [830, 730], [520, 1040]] } };
  const CRACK = "M305 -15L252 95L322 190L238 295L318 395L262 480L304 575";
  BP.define("breakup", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      whole: { type: "actor" },
      parts: { type: "list", min: 2, max: 3, of: { who: { type: "actor" } } },
      at: { type: "anchor" }, // the break
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const g = SLOTS[p.parts.length];
      return `${p.head ? `<div class="pad d bu-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${p.parts.map((q, i) => ACT.html(q.who, g.s, `bu-p bu-p${i}`, g.at[i][0], g.at[i][1])).join("")}
        ${ACT.html(p.whole, W[2], "bu-whole", W[0], W[1])}
        <div class="bu-ring" style="position:absolute;left:${W[0] - 60}px;top:${W[1] - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
        <div class="bu-flash" style="position:absolute;left:${W[0] - 170}px;top:${W[1] - 170}px;width:340px;height:340px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d bu-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 1.6), span = c.end - c.start, n = p.parts.length, g = SLOTS[n];
      const whole = c.q(".bu-whole .act-v"), parts = p.parts.map((_, i) => c.q(`.bu-p${i} .act-v`));
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 81, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".bu-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".bu-whole"), { scale: 0.65, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      tl.set(c.sel(".bu-p"), { autoAlpha: 0 }, 0);
      // the shatter has to clone the whole before the crack line is added, so the shards stay clean
      ACT.shatter(c, ".bu-whole", t, { ix: 0.55, iy: 0.5, sectors: 7, seed: 19, force: 300, dur: 1.0, gravity: c.L.id === "space" ? 140 : 480 });
      const crack = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      crack.setAttribute("width", W[2]); crack.setAttribute("height", W[2]); Object.assign(crack.style, { position: "absolute", left: 0, top: 0, overflow: "visible" });
      crack.innerHTML = `<path d="${CRACK}" fill="none" stroke="var(--accent)" stroke-width="16" stroke-linejoin="miter" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>`;
      whole.appendChild(crack);
      tl.fromTo(crack.firstChild, { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.9, ease: "power2.in", immediateRender: false }, t - 1.0);
      c.sfx(t - 1.0, "scratch", { dur: 0.7, gain: 0.14 }); c.sfx(t - 1.4, "riser", { dur: 1.4, gain: 0.14 });
      tl.to(c.sel(".bu-whole .act-name"), { autoAlpha: 0, duration: 0.2 }, t - 0.4);
      // the parts burst out of the break and settle into their places
      p.parts.forEach((_, i) => {
        const [x, y] = g.at[i], s = c.sel(`.bu-p${i}`), d = Math.hypot(x - W[0], y - W[1]) / 520;
        tl.fromTo(s, { x: W[0] - x, y: W[1] - y, scale: 0.35, autoAlpha: 0 }, { x: 0, y: 0, scale: 1, autoAlpha: 1, duration: 0.55 + d * 0.5, ease: "back.out(1.3)", immediateRender: false }, t + 0.02);
        tl.fromTo(s, { rotation: (i % 2 ? 1 : -1) * 70 }, { rotation: 0, duration: 0.75, ease: "power3.out", immediateRender: false }, t + 0.02);
        tl.fromTo(c.sel(`.bu-p${i} .act-name`), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, t + 0.7);
        tl.to(s, { x: (x - W[0]) * 0.07, y: (y - W[1]) * 0.07, duration: Math.max(0.5, c.end - t - 1.2), ease: "none", data: "ambient" }, t + 1.2); // keep drifting apart
        c.sfx(t + 0.25 + i * 0.12, "pop", { step: 1 + i * 2, gain: 0.1 });
      });
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => {
        const u = c.start + o.t, amp = Math.max(0, Math.min(1, (u - (t - 1.4)) / 1.4)) * 7;
        if (u < t) whole.style.transform = `translate(${Math.sin(u * 61) * amp}px,${Math.cos(u * 47) * amp * 0.6}px) rotate(${Math.sin(u * 53) * amp * 0.25}deg)`;
        parts.forEach((e, i) => { e.style.transform = u < t + 0.9 ? "" : `translate(${Math.sin(u * 1.3 + i * 2) * 10}px,${Math.cos(u * 1.1 + i) * 14}px) rotate(${Math.sin(u + i * 1.7) * 3}deg)`; });
      } }, c.start);
      tl.fromTo(c.sel(".bu-ring"), { scale: 0.3, opacity: 1 }, { scale: 8, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".bu-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.7, duration: 0.32, ease: "power2.out", immediateRender: false }, t);
      tl.set(c.sel(".bu-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-20, 10], [16, -12], [-10, 6], [6, -3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 2.2, { at: t, x: W[0], y: W[1], spread: 3.1, g: c.L.id === "space" ? 120 : 600, count: 170, seed: 83, color: c.L.particles.accent });
      c.particles("dust", t, c.end, { count: 60, seed: 85, color: c.L.particles.dust });
      c.sfx(t, "impact"); c.sfx(t + 0.02, "whoosh-big", { dur: 0.6, gain: 0.16 });
      if (p.result) c.rise(".bu-result", p.resultAt ? c.at(p.resultAt) : t + 1.1, { ease: "power4.out" });
    },
  });
})();
