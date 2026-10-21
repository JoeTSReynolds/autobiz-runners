// 4..7 `nodes` (small actors) appear one by one and link up with lines drawing between them. On `signalAt` a
// signal leaves the `from` node (index, default the first) and ripples out through the links: a pulse runs along
// each, the link turns accent and each node it reaches flashes and keeps an accent ring. With a `fail` word the
// wave runs into `failNode` (index; default a middle one), which cracks, shatters and is crossed out exactly on
// that word, and the signal stops there: nodes beyond it stay dark and dim. A `result` line lands.
// Cast anything: an outage spreading through cloud regions (asset cloud x5, names "US East", "EU", "Asia"; fail),
// mission control relaying a signal through the deep space network (asset tower/satellite/planet/lander), a
// payment passing through banks (asset building x4), a rumour spreading between people (asset person x6).
const NET = { cx: 540, cy: 920, ring: [390, 380], edges: { 4: [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]], 5: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 0], [0, 2]], 6: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [0, 3]], 7: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [6, 0], [6, 2], [6, 4]] } };
NET.pos = (n, i) => { const r = n === 7 ? 6 : n; if (i >= r) return [NET.cx, NET.cy]; const a = -Math.PI / 2 + (2 * Math.PI * i) / r; return [NET.cx + NET.ring[0] * Math.cos(a), NET.cy + NET.ring[1] * Math.sin(a)]; };
NET.bfs = (n, from, fail) => { // depth of every node from `from`; with a failing node the wave does not go past it
  const d = Array(n).fill(-1), q = [from]; d[from] = 0;
  for (let h = 0; h < q.length; h++) for (const [a, b] of NET.edges[n]) for (const [u, v] of [[a, b], [b, a]]) if (u === q[h] && d[v] < 0 && q[h] !== fail) { d[v] = d[u] + 1; q.push(v); }
  return d;
};
BP.define("network", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    nodes: { type: "list", min: 4, max: 7, of: { who: { type: "actor" } } },
    from: { type: "number", min: 0, max: 6, opt: true }, signalAt: { type: "anchor" },
    fail: { type: "anchor", opt: true }, failNode: { type: "number", min: 0, max: 6, opt: true },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  validate(p) {
    const e = [], n = (p.nodes || []).length, f = p.from || 0;
    if (f >= n) e.push(`from ${f} is not a node (0..${n - 1})`);
    if (p.failNode !== undefined && (!p.fail || p.failNode >= n || p.failNode === f)) e.push("failNode needs a fail word, must be a node, and cannot be the from node");
    return e;
  },
  html(p) {
    const n = p.nodes.length, sz = 160, E = NET.edges[n];
    const line = (cls, [a, b], col, w) => { const [x1, y1] = NET.pos(n, a), [x2, y2] = NET.pos(n, b); return `<line class="${cls}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${col}" stroke-width="${w}" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>`; };
    return `${p.head ? `<div class="pad d nw-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      <svg style="position:absolute;left:0;top:0;overflow:visible" width="1080" height="1920">${E.map((e, j) => line(`nw-e nw-e${j}`, e, "var(--mid)", 5)).join("")}${E.map((e, j) => line(`nw-h nw-h${j}`, e, "var(--accent)", 9)).join("")}</svg>
      ${p.nodes.map((nd, i) => { const [x, y] = NET.pos(n, i); return ACT.html(nd.who, sz, `nw-n nw-n${i}`, x, y) + `<i class="nw-l nw-l${i}" style="position:absolute;left:${x - sz / 2 - 18}px;top:${y - sz / 2 - 18}px;width:${sz + 36}px;height:${sz + 36}px;border-radius:50%;border:8px solid var(--accent);opacity:0"></i>`; }).join("")}
      ${p.nodes.map((nd, i) => { const [x, y] = NET.pos(n, i); return `<div class="nw-x nw-x${i}" style="position:absolute;left:${x - 70}px;top:${y - 70}px;width:140px;height:140px;opacity:0"><i style="position:absolute;left:0;top:62px;width:140px;height:16px;background-color:var(--accent);transform:rotate(45deg)"></i><i style="position:absolute;left:0;top:62px;width:140px;height:16px;background-color:var(--accent);transform:rotate(-45deg)"></i></div>`; }).join("")}
      ${p.result ? `<div class="pad d nw-result" style="top:372px;font-size:96px;color:var(--accent-text)"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, n = p.nodes.length, E = NET.edges[n], from = p.from || 0, sz = 160, tN = (i) => c.start + 0.3 + i * 0.28;
    const tSig = Math.max(c.at(p.signalAt), tN(n - 1) + 0.9), d0 = NET.bfs(n, from, -1), maxD = Math.max(...d0);
    const fail = p.fail ? (p.failNode ?? d0.findIndex((d) => d === Math.max(1, Math.ceil(maxD / 2)))) : -1, d = NET.bfs(n, from, fail);
    const hop = fail >= 0 ? Math.min(1.6, Math.max(0.3, (Math.max(c.at(p.fail), tSig + 0.6) - tSig) / d[fail])) : Math.min(0.9, Math.max(0.3, (c.end - tSig - 2.2) / (maxD || 1)));
    const arr = (i) => tSig + d[i] * hop, tF = fail >= 0 ? arr(fail) : 0, ar = (i) => `.nw-n${i}`;
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 33, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".nw-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    p.nodes.forEach((_, i) => { // nodes pop in; a link draws once both of its ends are there
      tl.fromTo(c.sel(ar(i)), { scale: 0.3, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.5, ease: "back.out(2)" }, tN(i));
      tl.fromTo(c.sel(`${ar(i)} .act-v`), { rotation: -4 }, { rotation: 4, duration: c.end - c.start, ease: "none", data: "ambient" }, c.start);
      c.sfx(tN(i), "pop", { step: i, dur: 0.12, gain: 0.08 });
    });
    E.forEach(([a, b], j) => { const t = Math.max(tN(a), tN(b)) + 0.1; tl.fromTo(c.sel(`.nw-e${j}`), { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.5, ease: "power2.out", immediateRender: false }, t); });
    c.sfx(tN(1), "whoosh", { dur: 0.8, gain: 0.07 });
    const ring = (i, t, big) => { // a node is reached: flash, ring stays on
      tl.fromTo(c.sel(`.nw-l${i}`), { scale: big ? 1.5 : 1.3, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, ease: "back.out(2)", immediateRender: false }, t);
      tl.fromTo(c.sel(`${ar(i)} .act-v`), { scale: 1 }, { scale: 1.18, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false, transformOrigin: "50% 50%" }, t);
      c.particles("burst", t - 0.05, t + 1.2, { at: t, x: NET.pos(n, i)[0], y: NET.pos(n, i)[1], spread: 3.1, g: 60, count: 28, seed: 90 + i, color: c.L.particles.accent });
    };
    c.sfx(tSig - 1.0, "riser", { dur: 1.0, gain: 0.1 });
    ring(from, tSig, true); c.sfx(tSig, "impact", { gain: 0.12 });
    E.forEach(([a, b], j) => { // pulses travel along the links the wave uses, from the nearer end to the farther
      const [u, v] = d[a] >= 0 && d[b] === d[a] + 1 ? [a, b] : d[b] >= 0 && d[a] === d[b] + 1 ? [b, a] : [-1, -1];
      if (u < 0 || (fail >= 0 && u === fail)) return;
      const [x1, y1] = NET.pos(n, u), [x2, y2] = NET.pos(n, v), t0 = arr(u), id = `nwp${j}`, h = c.sel(`.nw-h${j}`);
      const el = c.q(`.nw-h${j}`); el.setAttribute("x1", x1); el.setAttribute("y1", y1); el.setAttribute("x2", x2); el.setAttribute("y2", y2);
      tl.fromTo(h, { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: hop * 0.85, ease: "none", immediateRender: false }, t0);
      c.box.insertAdjacentHTML("beforeend", `<i class="${id}" style="position:absolute;left:${x1 - 16}px;top:${y1 - 16}px;width:32px;height:32px;border-radius:50%;background-color:var(--accent);opacity:0"></i>`);
      tl.fromTo(c.sel(`.${id}`), { x: 0, y: 0, autoAlpha: 1 }, { x: x2 - x1, y: y2 - y1, duration: hop * 0.85, ease: "none", immediateRender: false }, t0).set(c.sel(`.${id}`), { autoAlpha: 0 }, t0 + hop * 0.85);
    });
    const tree = E.map(([a, b], j) => (d[a] >= 0 && d[b] === d[a] + 1 ? [a, b, j] : d[b] >= 0 && d[a] === d[b] + 1 ? [b, a, j] : null)).filter((e) => e && e[0] !== fail); // links the wave used
    const dm = Math.max(...d), cyc = dm * hop + 0.9;
    for (let k = 1, t0 = tSig + cyc; t0 + dm * hop < c.end - 0.1 && k < 8; k++, t0 += cyc) tree.forEach(([u, v, j]) => { // after the wave a quiet pulse keeps running through the links
      const [x1, y1] = NET.pos(n, u), [x2, y2] = NET.pos(n, v), id = `nwq${k}_${j}`, ta = t0 + d[u] * hop;
      c.box.insertAdjacentHTML("beforeend", `<i class="${id}" style="position:absolute;left:${x1 - 11}px;top:${y1 - 11}px;width:22px;height:22px;border-radius:50%;background-color:var(--accent);opacity:0"></i>`);
      tl.fromTo(c.sel(`.${id}`), { x: 0, y: 0, autoAlpha: 1 }, { x: x2 - x1, y: y2 - y1, duration: hop * 0.85, ease: "none", immediateRender: false }, ta).set(c.sel(`.${id}`), { autoAlpha: 0 }, ta + hop * 0.85);
      if (v !== fail) tl.fromTo(c.sel(`.nw-l${v}`), { scale: 1 }, { scale: 1.12, duration: 0.18, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, ta + hop * 0.85);
    });
    p.nodes.forEach((_, i) => { if (i !== from && i !== fail && d[i] > 0) { ring(i, arr(i), false); c.sfx(arr(i), "blip", { step: d[i] + 1, dur: 0.25, gain: 0.09 }); } });
    if (fail >= 0) {
      const [fx, fy] = NET.pos(n, fail);
      ring(fail, tF, false);
      tl.set(c.sel(`.nw-l${fail}`), { opacity: 0 }, tF + 0.05);
      ACT.shatter(c, ar(fail), tF + 0.05, { seed: 23, force: 520, gravity: c.L.id === "space" ? 160 : 520 });
      tl.fromTo(c.sel(`.nw-x${fail}`), { scale: 0.3, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, ease: "back.out(3)", immediateRender: false }, tF + 0.15);
      p.nodes.forEach((_, i) => { if (d[i] < 0) tl.to(c.sel(ar(i)), { opacity: 0.35, duration: 0.5 }, tF + 0.3); });
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-18, 8], [14, -10], [-8, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tF + 0.05);
      c.particles("burst", tF, tF + 1.7, { at: tF + 0.05, x: fx, y: fy, spread: 3.1, g: 500, count: 120, seed: 99, color: c.L.particles.accent });
      c.sfx(tF + 0.05, "impact", { gain: 0.18 }); c.sfx(tF + 0.05, "whoosh-big", { dur: 0.6, gain: 0.14 });
    } else {
      const tA = tSig + maxD * hop + 0.3;
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-8, 5], [6, -5], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.06 })), immediateRender: false }, tA);
      c.sfx(tA, "chime", { step: 3, gain: 0.1 });
    }
    if (p.result) c.rise(".nw-result", p.resultAt ? c.at(p.resultAt) : (fail >= 0 ? tF : tSig + maxD * hop) + 0.8, { ease: "power4.out" });
  },
});
