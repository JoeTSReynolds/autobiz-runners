// 2..4 `racers` (each an actor with a `name` and a `score`) run up their own lanes towards a chequered finish line,
// bunched together at first and swapping the lead. On the `at` word the racer with the highest score lights up
// (an accent halo, the others dim), pulls ahead and crosses the line with a flash, a ring and a burst; the others
// settle in proportion to their scores. Each lane shows its score (with `unit`) counting up under the track.
// Give every racer a short `name`. A `result` line lands under the scores.
// Cast anything: an AI model leaderboard (racers asset robot "Model A" 87, label "Model B" 79, asset laptop
// "Model C" 64; unit "pts"), launches per country in a year (asset rocket "USA" 108, "China" 68, "Russia" 17;
// unit "launches"), chip makers by share (asset chip), rovers by distance driven.
(() => {
  const LX = 72, LW = 936, FY = 452, BOT = 1170, SY = 1180;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  BP.define("race", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      racers: { type: "list", min: 2, max: 4, of: { who: { type: "actor" }, score: { type: "number", min: 0, max: 999999999 } } },
      unit: { type: "text", max: 10, opt: true },
      at: { type: "anchor" }, // the leader pulls ahead
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const n = p.racers.length, w = LW / n, size = [0, 0, 420, 290, 220][n], light = p.ground === "light";
      const strip = Array.from({ length: Math.round(LW / 26) * 2 }, (_, i) => `<i style="position:absolute;left:${(i >> 1) * 26}px;top:${(i & 1) * 14}px;width:26px;height:14px;background-color:${((i >> 1) + (i & 1)) % 2 ? "currentColor" : "transparent"}"></i>`).join("");
      return `${p.head ? `<div class="pad d rc-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        <div class="rc-fin" style="position:absolute;left:${LX}px;top:${FY}px;width:${LW}px;height:28px;opacity:0">${strip}</div>
        ${Array.from({ length: n - 1 }, (_, i) => `<i class="rc-div" style="position:absolute;left:${LX + w * (i + 1) - 2}px;top:${FY + 40}px;width:4px;height:${BOT - FY - 40}px;background-color:var(--mid);opacity:0"></i>`).join("")}
        ${p.racers.map((r, i) => `<i class="rc-halo rc-halo${i}" style="position:absolute;left:0;top:0;width:${size + 36}px;height:${size + 36}px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>${ACT.html(r.who, size, `rc-r rc-r${i}`, 0, 0)}
          <div class="pad d rc-sc rc-sc${i}" style="left:${LX + w * i}px;right:auto;width:${w}px;top:${SY}px;text-align:center;white-space:nowrap;font-size:${n === 4 ? 84 : 100}px;color:${light ? "var(--ink)" : "var(--light)"};opacity:0;z-index:2"><span class="rc-n">${r.score.toLocaleString("en-US")}</span>${p.unit ? `<span style="font-size:${n === 4 ? 34 : 46}px;margin-left:10px;color:var(--mid)">${p.unit}</span>` : ""}</div>`).join("")}
        <i class="rc-ring" style="position:absolute;left:0;top:${FY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
        ${p.result ? `<div class="pad d rc-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, n = p.racers.length, w = LW / n, size = [0, 0, 420, 290, 220][n], span = c.end - c.start;
      const t = Math.max(c.at(p.at), c.start + 2.4), tS = c.start + 1.0, max = Math.max(...p.racers.map((r) => r.score)), lead = p.racers.findIndex((r) => r.score === max);
      const yTop = FY + 40 + size / 2, yBot = BOT - 94 - size / 2, cxs = p.racers.map((_, i) => LX + w * (i + 0.5));
      const st = p.racers.map(() => ({ p: 0 })), els = p.racers.map((_, i) => c.q(`.rc-r${i}`)), halos = p.racers.map((_, i) => c.q(`.rc-halo${i}`)), nEls = p.racers.map((_, i) => c.q(`.rc-sc${i} .rc-n`)), vs = p.racers.map((_, i) => c.q(`.rc-r${i} .act-v`));
      const fin = p.racers.map((r, i) => i === lead ? 1 : 0.45 + 0.4 * (r.score / max)), cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent, mid = c.L.colors.mid;
      let ph = 0, bob = 0;
      const yOf = (i) => yBot + (yTop - yBot) * st[i].p;
      const draw = () => {
        p.racers.forEach((r, i) => {
          const y = yOf(i), x = cxs[i] + Math.sin(ph * 6 + i * 2) * 4 * (st[i].p > 0 ? 1 : 0);
          Object.assign(els[i].style, { left: x - size / 2 + "px", top: y - size / 2 + "px" });
          Object.assign(halos[i].style, { left: x - (size + 36) / 2 + "px", top: y - (size + 36) / 2 + "px" });
          nEls[i].textContent = Math.round(r.score * clamp(st[i].p / fin[i])).toLocaleString("en-US");
        });
        cx.clearRect(0, 0, 1080, 1920); // speed streaks falling past each lane, faster once they are running
        const run = clamp((ph - tS) / 1.0);
        if (run > 0) for (let i = 0; i < n; i++) for (let k = 0; k < 7; k++) {
          const sp = (260 + 160 * ((k * 53) % 7) / 7) * (0.4 + 0.6 * run) * (i === lead && ph > t ? 1.8 : 1), yy = FY + 60 + (((k * 211 + ph * sp) % (BOT - FY - 80)) + (BOT - FY - 80)) % (BOT - FY - 80);
          cx.globalAlpha = 0.55; cx.fillStyle = i === lead && ph > t ? acc : mid; cx.fillRect(LX + w * i + 22 + ((k * 97) % Math.max(10, w - 60)), yy, 6, 46 + (k % 3) * 20);
        }
        cx.globalAlpha = 1;
      };
      draw();
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 201, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".rc-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".rc-fin"), { opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, duration: 0.6, ease: "power3.out" }, c.start + 0.1);
      tl.fromTo(c.sel(".rc-div"), { opacity: 0 }, { opacity: 0.6, duration: 0.4, stagger: 0.1 }, c.start + 0.2);
      p.racers.forEach((_, i) => {
        tl.fromTo(c.sel(`.rc-r${i}`), { scale: 0.5, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "back.out(1.7)" }, c.start + 0.3 + i * 0.15);
        tl.fromTo(c.sel(`.rc-sc${i}`), { autoAlpha: 0, y: 30 }, { autoAlpha: 1, y: 0, duration: 0.5, ease: "power3.out" }, c.start + 0.5 + i * 0.15);
        c.sfx(c.start + 0.3 + i * 0.15, "pop", { step: i * 2, gain: 0.1 });
        // bunched at first, swapping the lead (a different wobble per racer), all level at the word
        const d = t - tS, pos = (k) => 0.14 + 0.05 * (((i + k) % n) / Math.max(1, n - 1));
        tl.fromTo(st[i], { p: 0 }, { keyframes: [{ p: pos(0), duration: d * 0.3, ease: "sine.inOut" }, { p: pos(1) + 0.12, duration: d * 0.35, ease: "sine.inOut" }, { p: 0.42, duration: d * 0.35, ease: "sine.inOut" }], onUpdate: draw, immediateRender: false }, tS);
        tl.fromTo(st[i], { p: 0.42 }, { p: fin[i], duration: i === lead ? 1.1 : 1.0, ease: i === lead ? "power3.inOut" : "power2.out", onUpdate: draw, immediateRender: false }, t);
        if (i !== lead) tl.to(vs[i], { opacity: 0.5, duration: 0.4 }, t);
      });
      c.sfx(tS, "whoosh", { dur: 0.7, gain: 0.12 }); c.sfx(tS, "riser", { dur: t - tS, gain: 0.14 });
      // the leader lights up and crosses the line
      tl.fromTo(halos[lead], { autoAlpha: 0, scale: 0.8 }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: "back.out(2)", immediateRender: false }, t);
      tl.fromTo(c.sel(`.rc-r${lead}`), { scale: 1 }, { scale: 1.08, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t + 0.9);
      const tf = t + 1.1;
      tl.fromTo(c.sel(".rc-ring"), { scale: 0.3, opacity: 1, x: cxs[lead] - 60 }, { scale: 7, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, tf);
      tl.fromTo(c.sel(".rc-fin"), { scaleY: 1 }, { scaleY: 2.2, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tf);
      tl.fromTo(c.sel(`.rc-sc${lead}`), { scale: 1, color: "var(--accent-text)" }, { scale: 1.14, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tf);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tf);
      c.particles("burst", tf - 0.05, tf + 1.9, { at: tf, x: cxs[lead], y: FY + 14, spread: 2.2, dir: Math.PI / 2, g: 600, count: 160, seed: 203, color: c.L.particles.accent });
      c.sfx(t, "whoosh-big", { dur: 0.9, gain: 0.16 }); c.sfx(tf, "impact"); c.sfx(tf + 0.05, "chime", { step: 3, gain: 0.12 });
      for (let u = c.start + 1.4; u < c.end - 0.5; u += 2.4) if (Math.abs(u - tf) > 0.7) tl.fromTo(c.sel(".rc-ring"), { scale: 0.3, opacity: 0.5, x: cxs[lead] - 60 }, { scale: 4, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => { ph = c.start + o.t; vs.forEach((e, i) => { e.style.transform = `rotate(${Math.sin(ph * 5 + i * 2) * 3 * (st[i].p > 0.02 ? 1 : 0)}deg)`; }); draw(); } }, c.start);
      if (p.result) c.rise(".rc-result", p.resultAt ? c.at(p.resultAt) : tf + 1.0, { ease: "power4.out" });
    },
  });
})();
