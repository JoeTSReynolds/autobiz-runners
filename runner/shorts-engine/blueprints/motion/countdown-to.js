// A big calendar panel spins its `date` forward like a slot machine: every character is a reel of rolling digits
// or letters that slows and clicks into place, left to right, the last one landing exactly on the `at` word. In
// the same instant the `subject` actor (waiting inside a turning dashed ring) is swapped for its end state, the
// `after` actor, with a flash, rings and a burst; the date locks in accent. Afterwards the new actor keeps pinging.
// `date` is up to 12 characters ("Aug 2027", "14 MAR", "2027", "Q3 2026"). A `result` line lands under it.
// Cast anything: a product's launch day (subject asset phone named "Prototype" -> after asset phone tint accent
// named "On sale", date "12 SEP"), arrival at Mars in August 2027 (subject asset rocket -> after asset lander,
// date "Aug 2027"), a deadline (subject asset document -> asset shield), a chip leaving the fab (asset chip).
(() => {
  const SC = [540, 1000, 420], PX = 72, PW = 936, PY = 410, PH = 300, BAND = 56;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const kind = (ch) => (/[0-9]/.test(ch) ? "d" : /[A-Z]/.test(ch) ? "u" : /[a-z]/.test(ch) ? "l" : ch === " " ? "s" : "p");
  const wf = { d: 0.66, u: 0.68, l: 0.56, s: 0.3, p: 0.34 };
  const pool = { d: "0123456789", u: "ABCDEFGHIJKLMNOPQRSTUVWXYZ", l: "abcdefghijklmnopqrstuvwxyz" };
  BP.define("countdown-to", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      subject: { type: "actor" }, after: { type: "actor" },
      date: { type: "text", max: 12 },
      at: { type: "anchor" }, // the date lands and the subject becomes its end state
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const chars = [...p.date], F = Math.min(190, Math.floor(830 / chars.reduce((s, ch) => s + wf[kind(ch)], 0))), H = Math.round(F * 1.08);
      const light = p.ground === "light", bg = light ? "var(--ink)" : "var(--light)", fg = light ? "var(--light)" : "var(--dark)", total = chars.reduce((s, ch) => s + Math.round(wf[kind(ch)] * F), 0);
      const top = PY + BAND + (PH - BAND - H) / 2;
      let x = PX + (PW - total) / 2, seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      const cells = chars.map((ch, i) => {
        const k = kind(ch), w = Math.round(wf[k] * F), steps = pool[k] ? 16 + i * 4 : 0;
        const seq = Array.from({ length: steps }, () => pool[k][Math.floor(rnd() * pool[k].length)]).concat(ch);
        const el = `<div class="cd-cell" data-steps="${steps}" style="position:absolute;left:${x}px;top:${top}px;width:${w}px;height:${H}px;overflow:hidden"><div class="cd-strip d" data-layout-allow-overflow style="position:absolute;left:0;top:0;width:${w}px;font-size:${F}px;color:${fg};text-align:center">${seq.map((s) => `<div style="height:${H}px;line-height:${H}px">${s}</div>`).join("")}</div></div>`;
        x += w; return el;
      });
      return `${p.head ? `<div class="pad d cd-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        <div class="cd-panel" style="position:absolute;left:${PX}px;top:${PY}px;width:${PW}px;height:${PH}px;background-color:${bg}"><i style="position:absolute;left:0;top:0;width:100%;height:${BAND}px;background-color:var(--accent)"></i></div>
        ${[PX + 150, PX + PW - 190].map((x0) => `<i class="cd-hole" style="position:absolute;left:${x0}px;top:${PY - 24}px;width:40px;height:62px;background-color:${bg};border:8px solid var(--accent)"></i>`).join("")}
        <div class="cd-reels" style="position:absolute;left:0;top:0">${cells.join("")}</div>
        ${ACT.html(p.after, SC[2], "cd-after", SC[0], SC[1])}${ACT.html(p.subject, SC[2], "cd-subj", SC[0], SC[1])}
        <div class="cd-ring" style="position:absolute;left:${SC[0] - 60}px;top:${SC[1] - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
        <div class="cd-flash" style="position:absolute;left:${SC[0] - 200}px;top:${SC[1] - 200}px;width:400px;height:400px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d cd-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 1.8), span = c.end - c.start, cells = [...c.qa(".cd-cell")], n = cells.length;
      const spin = Math.min(3.2, t - c.start - 0.9), ts = t - spin, H = cells[0].offsetHeight;
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent;
      c.box.appendChild(cv); cv.style.zIndex = 1;
      const strips = cells.map((e) => e.firstChild), steps = cells.map((e) => +e.dataset.steps), sv = c.q(".cd-subj .act-v");
      const landed = cells.map(() => false);
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        cells.forEach((e, i) => {
          const te = t - (n - 1 - i) * 0.1, u = clamp((tt - ts) / (te - ts)), done = u >= 1;
          strips[i].style.transform = `translateY(${-steps[i] * (1 - (1 - u) ** 3) * H}px)`;
          if (done !== landed[i]) { landed[i] = done; [...strips[i].children].forEach((r, k, all) => (r.style.visibility = done && k < all.length - 1 ? "hidden" : "visible")); } // a landed reel shows only its final character
        });
        if (tt < t) { // the subject waits inside a turning dashed ring that tightens as the date nears
          const k = clamp((tt - ts) / spin); cx.strokeStyle = acc; cx.lineWidth = 9; cx.setLineDash([26, 22]); cx.lineDashOffset = -tt * 90 * (1 + 2 * k);
          cx.beginPath(); cx.arc(SC[0], SC[1], 245 - 25 * k, 0, 6.283); cx.stroke(); cx.setLineDash([]);
          sv.style.transform = `translate(${Math.sin(tt * 60) * 5 * k}px,${Math.cos(tt * 50) * 3 * k}px)`;
        } else {
          sv.style.transform = "";
          for (let q = 0; q < 2 && tt > t + 0.9; q++) { const age = ((tt - t - 0.9 + q * 0.75) % 1.5) / 1.5; cx.globalAlpha = 0.6 * (1 - age); cx.strokeStyle = acc; cx.lineWidth = 6; cx.beginPath(); cx.arc(SC[0], SC[1], 215 + 70 * age, 0, 6.283); cx.stroke(); }
          cx.globalAlpha = 1;
        }
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 131, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".cd-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".cd-panel"), { scaleX: 0, transformOrigin: "50% 50%" }, { scaleX: 1, duration: 0.6, ease: "power3.out" }, c.start + 0.05);
      tl.fromTo(c.sel(".cd-hole"), { autoAlpha: 0, y: 30 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "back.out(2)", stagger: 0.1 }, c.start + 0.4);
      tl.fromTo(c.sel(".cd-reels"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, c.start + 0.5);
      tl.fromTo(c.sel(".cd-subj"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.3);
      tl.set(c.sel(".cd-after"), { autoAlpha: 0 }, 0);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.4, "pop", { step: 1 });
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      // the reels click as they roll and settle one by one
      c.sfx(ts, "riser", { dur: spin, gain: 0.12 }); c.sfx(ts, "whoosh", { f0: 300, f1: 1800, dur: 0.6, gain: 0.08 });
      for (let k = 0; k < 16; k++) c.sfx(ts + spin * (1 - (1 - k / 16) ** 1.6) * 0.95, "click", { gain: 0.06, f0: 1500 + k * 90 });
      cells.forEach((_, i) => c.sfx(t - (n - 1 - i) * 0.1, "pop", { step: i % 5, dur: 0.08, gain: 0.08 }));
      // the date locks in accent, the panel pops
      tl.set(c.sel(".cd-strip"), { color: p.ground === "light" ? "var(--accent)" : "var(--accent-deep)" }, t);
      tl.fromTo(c.sel(".cd-reels"), { scale: 1, transformOrigin: "50% 50%" }, { scale: 1.04, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
      // subject -> after
      tl.to(c.sel(".cd-subj"), { scale: 0.1, rotation: 140, autoAlpha: 0, duration: 0.3, ease: "power2.in", immediateRender: false }, t - 0.05);
      tl.fromTo(c.sel(".cd-after"), { scale: 0.1, autoAlpha: 0, rotation: -40 }, { scale: 1, autoAlpha: 1, rotation: 0, duration: 0.8, ease: "back.out(1.7)", immediateRender: false }, t + 0.15);
      tl.fromTo(c.sel(".cd-after .act-name"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, immediateRender: false }, t + 0.7);
      tl.fromTo(c.sel(".cd-ring"), { scale: 0.3, opacity: 1 }, { scale: 8, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".cd-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.7, duration: 0.35, ease: "power2.out", immediateRender: false }, t);
      tl.set(c.sel(".cd-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 1.9, { at: t, x: SC[0], y: SC[1], spread: 3.1, g: 300, count: 160, seed: 133, color: c.L.particles.accent });
      c.sfx(t, "impact", { gain: 0.16 }); c.sfx(t + 0.1, "chime", { step: 3, gain: 0.1 });
      if (p.result) {
        const r = p.resultAt ? c.at(p.resultAt) : t + 1.1;
        tl.to(c.sel(".cd-after .act-name"), { autoAlpha: 0, duration: 0.25 }, r - 0.45);
        c.rise(".cd-result", r, { ease: "power4.out" });
      }
    },
  });
})();
