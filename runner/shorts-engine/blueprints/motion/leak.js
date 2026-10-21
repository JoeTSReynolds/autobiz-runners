// A large `container` actor cracks open and `item` actors spill out of it one by one, arc away and scatter to
// the sides, faster and faster, while a big running figure counts up. The count reaches `count` (with `unit`
// after it) exactly on the `at` word, where the container gushes: rings, a flash, a burst and a shake. The leak
// keeps trickling afterwards, so the frame never goes still. `startAt` (optional) is the word the first crack opens
// on. A `result` line lands under the figure.
// Cast anything: 80 help pages leaking prompts (container asset document, item asset envelope or packet, count 80,
// unit "prompts"), gas escaping a comet (container asset comet, item asset rock, label unit "tonnes"), secrets
// leaking from a server (container asset server, item asset key), coins draining from a vault (asset building).
(() => {
  const C = [540, 760, 460], SZ = 100, LIFE = 3.4, FLY = 0.8;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const CRACK = [["M105 460L150 392L118 330L172 268", 0], ["M355 460L312 398L346 332L292 264", 1]]; // in the container's own 460 px box
  const MOUTH = [[C[0] - 125, C[1] + 190], [C[0] + 125, C[1] + 190]];
  BP.define("leak", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      container: { type: "actor" }, item: { type: "actor" },
      count: { type: "number", min: 2, max: 999999999 }, unit: { type: "text", max: 12, opt: true },
      at: { type: "anchor" }, // the count lands on its total
      startAt: { type: "anchor", opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      return `${p.head ? `<div class="pad d lk-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(p.container, C[2], "lk-cont", C[0], C[1])}
        <div class="pad d lk-count" style="top:1150px;font-size:150px;text-align:center;white-space:nowrap;opacity:0"><span class="lk-n" style="color:var(--accent-text)">${p.count.toLocaleString("en-US")}</span><span style="font-size:72px;margin-left:24px">${p.unit || ""}</span></div>
        ${Array.from({ length: 52 }, (_, k) => ACT.html({ ...p.item, name: undefined }, SZ, `lk-i lk-i${k}`, SZ / 2, SZ / 2)).join("")}
        ${MOUTH.map(([x, y], i) => `<div class="lk-ring lk-ring${i}" style="position:absolute;left:${x - 60}px;top:${y - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>`).join("")}
        ${p.result ? `<div class="pad d lk-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, tA = Math.max(c.at(p.at), c.start + 2.2), tS = Math.min(p.startAt ? c.at(p.startAt) : c.start + 1.1, tA - 1.4), span = c.end - c.start;
      let seed = 23; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      // births: speeding up until the count lands, then a steady trickle
      const pre = Math.min(26, Math.floor((tA - tS) / 0.14)), births = [];
      for (let k = 0; k < pre; k++) births.push(tS + (tA - tS - 0.15) * (k / pre) ** 0.75);
      for (let t = tA; t < c.end - 0.6 && births.length < 52; t += 0.34) births.push(t);
      const ytop = p.head ? 440 : 340, items = births.map((tb, k) => {
        const side = k % 2, x = side ? 840 + rnd() * 150 : 90 + rnd() * 150, y = ytop + (((k * 0.618 + rnd() * 0.2) % 1) * (1090 - ytop));
        return { tb, side, x, y, spin: (rnd() - 0.5) * 540 };
      });
      const els = items.map((_, k) => c.q(`.lk-i${k}`));
      els.forEach((e) => (e.style.visibility = "hidden"));
      c.qa(".lk-i").forEach((e, k) => { if (k >= items.length) e.remove(); });
      const cv = kit.canvas("#" + c.box.id).getContext("2d"), acc = `rgb(${c.L.particles.accent})`, dust = `rgb(${c.L.particles.dust})`;
      const cont = c.q(".lk-cont .act-v"), nEl = c.q(".lk-n"), count = c.q(".lk-count"), n = (v) => v.toLocaleString("en-US");
      const cracks = CRACK.map(([d], i) => { // jagged cracks drawn over the container, one per mouth
        const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        s.setAttribute("width", C[2]); s.setAttribute("height", C[2]); Object.assign(s.style, { position: "absolute", left: 0, top: 0, overflow: "visible" });
        s.innerHTML = `<path d="${d}" fill="none" stroke="var(--ab)" stroke-width="12" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>`;
        cont.appendChild(s); return s.firstChild;
      });
      const prog = (t) => clamp((t - tS) / (tA - tS)) ** 1.35;
      const frame = (t) => {
        cv.clearRect(0, 0, 1080, 1920);
        const pr = prog(t), amp = t < tS - 0.3 ? 0 : 1.2 + 2.4 * pr + (t > tA && t < tA + 0.5 ? 3 : 0);
        cont.style.transform = `translate(${Math.sin(t * 53) * amp * 2}px,${Math.cos(t * 41) * amp}px) rotate(${Math.sin(t * 37) * amp * 0.6}deg) scale(${1 - 0.07 * pr})`;
        if (t >= tS) for (let j = 0; j < 30; j++) { // a hissing spray at both mouths
          const f = t * 2.6 + j * 0.37, ph = f - Math.floor(f), m = MOUTH[j % 2], a = Math.PI / 2 + (j % 2 ? 1 : -1) * (0.35 + ((j * 7919) % 100) / 100 * 0.9), r = 20 + 190 * ph ** 0.7;
          cv.globalAlpha = (1 - ph) * (t > tA + 1 ? 0.5 : 0.9); cv.fillStyle = j % 3 ? acc : dust;
          cv.fillRect(m[0] + Math.cos(a) * r, m[1] + Math.sin(a) * r * 0.9, 9 - ph * 6, 9 - ph * 6);
        }
        cv.globalAlpha = 1;
        nEl.textContent = n(t >= tA ? p.count : Math.round(p.count * pr));
        items.forEach((it, k) => {
          const age = t - it.tb, e = els[k];
          if (age < 0 || age > LIFE) { e.style.visibility = "hidden"; return; }
          const u = clamp(age / FLY), q = 1 - (1 - u) ** 3, m = MOUTH[it.side];
          const x = m[0] + (it.x - m[0]) * q, y = m[1] + (it.y - m[1]) * q - 150 * Math.sin(Math.PI * u) + (u >= 1 ? Math.sin(t * 2.2 + k) * 7 : 0);
          const s = Math.min(u * 3, 1) * (1 - clamp((age - (LIFE - 0.4)) / 0.4));
          Object.assign(e.style, { visibility: "visible", transform: `translate(${x - SZ / 2}px,${y - SZ / 2}px) rotate(${it.spin * (1 - (1 - u) ** 2)}deg) scale(${s})` });
        });
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 71, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".lk-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".lk-cont"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      tl.fromTo(count, { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: "power3.out" }, Math.max(c.start + 0.3, tS - 0.3));
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      // the cracks open: the first at the start word, the second halfway to the count
      [[tS - 0.2, 0.3], [tS + (tA - tS) * 0.45, 0.3]].forEach(([t, d], i) => {
        tl.fromTo(cracks[i], { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: d, ease: "power2.in", immediateRender: false }, t);
        c.sfx(t, "scratch", { dur: 0.35, gain: 0.14 });
      });
      c.sfx(tS - 0.3, "riser", { dur: tA - tS + 0.3, gain: 0.12 });
      items.forEach((it, k) => { if (k % 2 === 0 && it.tb < tA) c.sfx(it.tb, "pop", { step: k % 5, dur: 0.1, gain: 0.07 }); });
      // the gush on the count word
      MOUTH.forEach((m, i) => tl.fromTo(c.sel(`.lk-ring${i}`), { scale: 0.3, opacity: 1 }, { scale: 6, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, tA));
      tl.fromTo(count, { scale: 1, transformOrigin: "50% 50%" }, { scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tA);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tA);
      MOUTH.forEach((m, i) => c.particles("burst", tA - 0.05, tA + 1.7, { at: tA, x: m[0], y: m[1], spread: 1.8, dir: Math.PI / 2 + (i ? -0.7 : 0.7), g: 500, count: 90, seed: 73 + i, color: c.L.particles.accent }));
      c.sfx(tA, "impact", { gain: 0.16 }); c.sfx(tA + 0.05, "chime", { step: 3, gain: 0.1 });
      if (p.result) {
        const r = p.resultAt ? c.at(p.resultAt) : tA + 0.8;
        c.rise(".lk-result", r, { ease: "power4.out" });
      }
    },
  });
})();
