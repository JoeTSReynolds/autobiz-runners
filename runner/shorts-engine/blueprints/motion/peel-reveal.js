// A framed `cover` panel (an actor on a card) hides a `hidden` actor underneath. A glint sweeps the card, then it
// starts to give: with `how: "peel"` (default) a corner curls back along a diagonal fold, with `how: "shutter"` the
// card is cut into slats that rattle. On the `at` word it is ripped away (the peeled sheet flips off, or the slats
// fly out left and right) and the `hidden` actor is revealed with a glint, a ring and a burst, then keeps glinting
// and pinging. Optional `label` is a tag that snaps onto the hidden actor. A `result` line lands under it.
// Cast anything: a help page hiding instructions (cover asset document named "Help page", hidden asset robot
// with label "System prompt"), an ice crust over an ocean (cover asset planet tint light "Ice" -> hidden
// asset planet tint accent, label "Ocean"), a locked box with a prize (cover asset lock -> hidden asset coin),
// a rock face hiding a lander (cover asset rock -> image of the site).
(() => {
  const S = 560, CX = 540, CY = 810, X0 = CX - S / 2, Y0 = CY - S / 2, HS = 500;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const poly = (pts) => pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(",");
  BP.define("peel-reveal", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      cover: { type: "actor" }, hidden: { type: "actor" },
      at: { type: "anchor" }, // the reveal
      how: { type: "enum", values: ["peel", "shutter"], opt: true },
      label: { type: "text", max: 14, opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const bg = p.ground === "light" ? "var(--light)" : "var(--dark)", name = p.cover.name;
      return `${p.head ? `<div class="pad d pr-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        <div class="pr-well" style="position:absolute;left:${X0}px;top:${Y0}px;width:${S}px;height:${S}px;background-color:currentColor;opacity:0.12"></div>
        ${ACT.html(p.hidden, HS, "pr-hid", CX, CY)}
        <div class="pr-gl" style="position:absolute;left:${X0}px;top:${Y0}px;width:${S}px;height:${S}px;overflow:hidden;pointer-events:none"><i class="pr-gb" style="position:absolute;left:0;top:-120px;width:90px;height:${S + 240}px;background-color:#fff;opacity:0.8;transform:translateX(-300px) rotate(18deg)"></i></div>
        <div class="pr-sheet" style="position:absolute;left:${X0}px;top:${Y0}px;width:${S}px;height:${S}px">
          <div class="pr-card" style="position:absolute;inset:0;background-color:${bg};border:8px solid var(--accent);overflow:hidden">
            ${ACT.html({ ...p.cover, name: undefined }, 380, "pr-cv", S / 2 - 8, 240)}
            ${name ? `<div class="t" style="position:absolute;left:0;right:0;top:446px;text-align:center;font-size:46px;color:var(--accent-text)">${name}</div>` : ""}
            <i class="pr-cg" style="position:absolute;left:0;top:-120px;width:80px;height:${S + 240}px;background-color:currentColor;opacity:0.22;transform:translateX(-300px) rotate(18deg)"></i>
          </div>
          <svg class="pr-flap" width="${S}" height="${S}" style="position:absolute;left:0;top:0;overflow:visible"><polygon class="pr-fp" fill="var(--mid)" points="0,0"/><polygon class="pr-fs" fill="${p.ground === "light" ? "var(--ink)" : "var(--light)"}" opacity="0.5" points="0,0"/><line class="pr-fl" stroke="var(--accent)" stroke-width="8" x1="0" y1="0" x2="0" y2="0"/></svg>
        </div>
        ${p.label ? `<div class="d pr-tag" style="position:absolute;left:${CX - 190}px;top:${CY + 140}px;width:380px;height:84px;display:flex;align-items:center;justify-content:center;background-color:var(--accent);color:var(--ink);font-size:56px;white-space:nowrap;opacity:0">${p.label}</div>` : ""}
        <div class="pr-ring" style="position:absolute;left:${CX - 60}px;top:${CY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
        ${p.result ? `<div class="pad d pr-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 1.8), span = c.end - c.start, shutter = p.how === "shutter";
      const tp = Math.max(c.start + 1.0, t - 1.5), card = c.q(".pr-card"), fp = c.q(".pr-fp"), fs = c.q(".pr-fs"), fl = c.q(".pr-fl"), hv = c.q(".pr-hid .act-v");
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent;
      c.box.appendChild(cv); cv.style.zIndex = 1;
      const peel = (u) => { // the card is the part of the square on the near side of x + y = k; the flap is the corner folded back over it
        const k = 2 * S - S * u * u, e = k - S, L = S - 56;
        card.style.clipPath = `polygon(${poly([[0, 0], [S, 0], [S, e], [e, S], [0, S]])})`;
        const A = [e, S], B = [S, e], C = [e, e];
        fp.setAttribute("points", poly([A, B, C]));
        fs.setAttribute("points", poly(e >= L ? [A, B, [L, e], [e, L]] : [A, B, C]));
        fl.setAttribute("x1", A[0]); fl.setAttribute("y1", A[1]); fl.setAttribute("x2", B[0]); fl.setAttribute("y2", B[1]);
      };
      const slats = [];
      if (shutter) {
        for (let i = 0; i < 6; i++) { const s = card.cloneNode(true); s.className = "pr-slat"; s.style.clipPath = `inset(${(i * 100) / 6}% 0 ${((5 - i) * 100) / 6}% 0)`; card.parentNode.insertBefore(s, card); slats.push(s); }
        card.style.display = "none";
      }
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        if (!shutter) peel(tt < tp ? 0 : clamp((tt - tp) / (t - tp)));
        if (tt > t + 0.9) for (let k = 0; k < 2; k++) { // the revealed actor keeps pinging
          const age = ((tt - t - 0.9 + k * 0.75) % 1.5) / 1.5; cx.globalAlpha = 0.6 * (1 - age); cx.strokeStyle = acc; cx.lineWidth = 6;
          cx.beginPath(); cx.arc(CX, CY, 260 + 140 * age, 0, 6.283); cx.stroke();
        }
        cx.globalAlpha = 1;
        hv.style.transform = tt > t + 0.5 ? `translateY(${Math.sin(tt * 1.7) * 9}px) rotate(${Math.sin(tt * 1.2) * 2}deg)` : "";
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 101, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".pr-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".pr-well"), { scale: 0.7, autoAlpha: 0 }, { scale: 1, autoAlpha: 0.12, duration: 0.7, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.fromTo(c.sel(".pr-hid"), { scale: 0.7, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.fromTo(c.sel(".pr-sheet"), { scale: 0.7, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.set(c.sel(".pr-hid .act-name"), { autoAlpha: 0 }, 0);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      // glints sweep the card while it waits (a peel's corner lifts, a shutter rattles)
      for (let g = c.start + 0.9, k = 0; g < tp - 0.4; g += 1.8, k++) { tl.fromTo(c.sel(".pr-cg"), { x: 0 }, { x: S + 500, duration: 0.7, ease: "power2.inOut", immediateRender: false }, g); c.sfx(g, "click", { f0: 3000, gain: 0.05 }); }
      c.sfx(tp - 0.1, "riser", { dur: t - tp + 0.1, gain: 0.15 });
      if (shutter) tl.fromTo(slats, { x: 0 }, { keyframes: [3, -3, 4, -4, 5, -5, 6, -6].map((x, i) => ({ x: i % 2 ? -x : x, duration: (t - tp) / 8 })), immediateRender: false, stagger: 0.02 }, tp);
      else c.sfx(tp, "scratch", { dur: t - tp, gain: 0.1 });
      // the rip
      if (shutter) {
        slats.forEach((s, i) => { tl.to(s, { x: (i % 2 ? 1 : -1) * 1150, rotation: (i % 2 ? 1 : -1) * 6, duration: 0.55, ease: "power3.in", immediateRender: false }, t + i * 0.04); tl.set(s, { autoAlpha: 0 }, t + 0.75); });
      } else {
        tl.to(c.sel(".pr-sheet"), { x: -(S + 500), y: -(S + 200), rotation: -38, duration: 0.55, ease: "power3.in", immediateRender: false }, t);
        tl.set(c.sel(".pr-sheet"), { autoAlpha: 0 }, t + 0.6);
      }
      tl.fromTo(c.sel(".pr-hid"), { scale: 0.92 }, { scale: 1.06, duration: 0.22, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".pr-hid .act-name"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, immediateRender: false }, t + 0.5);
      // glints sweep the revealed actor now and then
      for (let g = t + 0.1; g < c.end - 0.7; g += 2.2) tl.fromTo(c.sel(".pr-gb"), { x: -300 }, { x: S + 500, duration: 0.6, ease: "power2.inOut", immediateRender: false }, g);
      c.sfx(t + 0.1, "chime", { step: 3, gain: 0.1 }); c.sfx(t, "whoosh-big", { dur: 0.5, gain: 0.16 }); c.sfx(t, "impact", { gain: 0.16 });
      tl.fromTo(c.sel(".pr-ring"), { scale: 0.3, opacity: 1 }, { scale: 8, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 1.8, { at: t, x: CX, y: CY, spread: 3.1, g: 200, count: 150, seed: 103, color: c.L.particles.accent });
      if (p.label) {
        tl.fromTo(c.sel(".pr-tag"), { autoAlpha: 0, scale: 1.6, rotation: -14 }, { autoAlpha: 1, scale: 1, rotation: -4, duration: 0.35, ease: "back.out(2.4)", immediateRender: false }, t + 0.45);
        c.sfx(t + 0.45, "pop", { step: 4, gain: 0.12 });
      }
      if (p.result) c.rise(".pr-result", p.resultAt ? c.at(p.resultAt) : t + 1.2, { ease: "power4.out" });
    },
  });
})();
