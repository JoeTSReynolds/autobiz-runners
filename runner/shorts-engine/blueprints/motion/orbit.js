// Things circle a centre on elliptical paths, each leaving a fading trail. `orbiters` (1..3, each `who` an
// actor, optional `at` word when it joins) loop round the `centre` actor, nearer ones faster, passing behind
// and in front of it. With a `passer` + `captureAt` it is the capture story instead: the passer flies in on
// a straight line, on the capture word its path bends into orbit with a ring pulse and a shake, and its own
// orbit ring draws in. A `result` line lands under it. At most 3 orbiting actors in total.
// Cast anything: Phobos and Deimos around Mars (asset moon x2 -> asset planet, tint accent), an asteroid
// captured by Jupiter (passer asset asteroid, centre asset planet), satellites around Earth (asset satellite
// -> planet), users orbiting a platform (label "Users" -> asset cloud), a photo of a moon around a planet.
const OR = { cx: 540, cy: 860, K: 14, rings: [[[400, 255, -8]], [[330, 225, -8], [420, 270, 6]], [[320, 215, -8], [385, 245, 6], [430, 275, -3]]] };
BP.define("orbit", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    centre: { type: "actor" },
    orbiters: { type: "list", min: 1, max: 3, opt: true, of: { who: { type: "actor" }, at: { type: "anchor", opt: true } } },
    passer: { type: "actor", opt: true }, captureAt: { type: "anchor", opt: true },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  validate(p) {
    const e = [], n = (p.orbiters || []).length + (p.passer ? 1 : 0);
    if (!n) e.push("needs orbiters or a passer");
    if (n > 3) e.push("at most 3 orbiting actors including the passer");
    if (!!p.passer !== !!p.captureAt) e.push("passer and captureAt go together");
    return e;
  },
  html(p) {
    const all = [...(p.orbiters || []).map((o) => o.who), ...(p.passer ? [p.passer] : [])], sz = [0, 220, 190, 170][all.length];
    const ring = OR.rings[all.length - 1];
    return `${p.head ? `<div class="pad d or-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      <svg style="position:absolute;left:0;top:0;overflow:visible" width="1080" height="1920">${ring.map(([rx, ry, tt], i) => `<ellipse class="or-r${i}" cx="${OR.cx}" cy="${OR.cy}" rx="${rx}" ry="${ry}" transform="rotate(${tt} ${OR.cx} ${OR.cy})" fill="none" stroke="${p.passer && i === all.length - 1 ? "var(--accent)" : "var(--mid)"}" stroke-width="4" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>`).join("")}</svg>
      ${ACT.html(p.centre, 420, "or-centre", OR.cx, OR.cy)}
      ${all.map((a, i) => Array.from({ length: OR.K }, (_, k) => `<i class="or-d${i}" style="position:absolute;border-radius:50%;opacity:0;width:${Math.round(sz * 0.2 * (1 - k / OR.K)) + 4}px;height:${Math.round(sz * 0.2 * (1 - k / OR.K)) + 4}px;background-color:${p.passer && i === all.length - 1 ? "var(--accent)" : "currentColor"}"></i>`).join("") + ACT.html(a, sz, `or-a${i}`, 0, 0)).join("")}
      <div class="or-ring" style="position:absolute;left:${OR.cx - 60}px;top:${OR.cy - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
      ${p.result ? `<div class="pad d or-result" style="top:1325px;font-size:96px;color:var(--accent-text)"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, orb = p.orbiters || [], n = orb.length + (p.passer ? 1 : 0), ring = OR.rings[n - 1], span = c.end - c.start, sz = [0, 220, 190, 170][n];
    const tc = p.passer ? c.at(p.captureAt) : 0, tIn0 = Math.max(c.start + 0.15, tc - 2.6), L = 720;
    const tIn = [...orb.map((o, i) => (o.at ? c.at(o.at) : c.start + 0.9 + i * 0.8)), tIn0];
    const w = (i) => (Math.PI * 2) / (6 + 2.5 * i), a0 = [0.6, 3.2, 5.1];
    const ell = (i, a) => { const [rx, ry, d] = ring[i], q = (d * Math.PI) / 180, x = rx * Math.cos(a), y = ry * Math.sin(a); return { x: OR.cx + x * Math.cos(q) - y * Math.sin(q), y: OR.cy + x * Math.sin(q) + y * Math.cos(q), z: Math.sin(a) }; };
    const E = p.passer ? ell(n - 1, -Math.PI / 2) : null, E2 = p.passer ? ell(n - 1, -Math.PI / 2 + 0.01) : null;
    const dl = p.passer ? Math.hypot(E2.x - E.x, E2.y - E.y) : 1, V = p.passer ? [((E2.x - E.x) / dl) * (L / (tc - tIn0)), ((E2.y - E.y) / dl) * (L / (tc - tIn0))] : 0;
    const pos = (i, t) => { // where actor i is at time t; hidden until it has joined
      const P = p.passer && i === n - 1 ? (() => {
        const lin = { x: E.x + V[0] * (t - tc), y: E.y + V[1] * (t - tc), z: 1 };
        if (t <= tc) return lin;
        const u = Math.min(1, (t - tc) / 1.3), s = u * u * (3 - 2 * u), o = ell(i, -Math.PI / 2 + w(i) * (t - tc));
        return { x: lin.x + (o.x - lin.x) * s, y: lin.y + (o.y - lin.y) * s, z: lin.z + (o.z - lin.z) * s };
      })() : ell(i, a0[i] + w(i) * (t - c.start));
      return { ...P, on: t >= tIn[i] };
    };
    const els = tIn.slice(0, n).map((_, i) => ({ a: c.q(`.or-a${i}`), v: c.q(`.or-a${i} .act-v`), n: c.q(`.or-a${i} .act-name`), d: [...c.qa(`.or-d${i}`)] }));
    const cn = c.q(".or-centre .act-name");
    const frame = (t) => { let hit = 0; els.forEach((e, i) => {
      const P = pos(i, t);
      Object.assign(e.a.style, { left: P.x - e.a.offsetWidth / 2 + "px", top: P.y - e.a.offsetHeight / 2 + "px", zIndex: P.z > 0 ? 3 : 1 });
      e.v.style.transform = `scale(${0.91 + 0.09 * P.z})`;
      if (e.n) e.n.style.opacity = P.on && Math.hypot(P.x - OR.cx, P.y + sz / 2 + 45 - OR.cy) > 290 && !(p.passer && i === n - 1 && t < tc + 0.7) ? 1 : 0; // a name never sits on the centre or on a planet it crosses
      e.d.forEach((d, k) => { const Q = pos(i, t - (k + 1) * 0.055); Object.assign(d.style, { left: Q.x - d.offsetWidth / 2 + "px", top: Q.y - d.offsetHeight / 2 + "px", opacity: Q.on && P.on ? (1 - k / OR.K) * 0.55 : 0, zIndex: Q.z > 0 ? 3 : 1 }); });
      if (P.on && Math.abs(P.x - OR.cx) < 260 && Math.abs(P.y - OR.cy - 250) < 150) hit = 1;
    }); if (cn) cn.style.opacity = hit ? 0 : 1; }; // the centre's name steps aside while an orbiter crosses it
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 120, seed: 9, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".or-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    tl.fromTo(c.sel(".or-centre"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
    tl.fromTo(c.sel(".or-centre .act-v"), { rotation: -5 }, { rotation: 5, duration: span, ease: "none", data: "ambient" }, c.start);
    c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
    const o = { t: 0 };
    tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
        const join = (i, t, x, y) => {
      tl.fromTo(c.sel(`.or-a${i}`), { scale: 0.2, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "back.out(2)" }, t);
      tl.fromTo(c.sel(`.or-r${i}`), { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.1, ease: "power2.inOut", immediateRender: false }, t); c.sfx(t, "pop", { step: 2 + i });
      c.particles("burst", t - 0.05, t + 1.5, { at: t, x, y, spread: 3.1, g: -40, count: 40, seed: 31 + i, color: c.L.particles.dust });
    };
    orb.forEach((_, i) => { const P = pos(i, tIn[i] + 0.3); join(i, tIn[i], P.x, P.y); });
    if (p.passer) {
      const i = n - 1, A = c.sel(`.or-a${i}`);
      tl.fromTo(A, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, tIn0);
      c.sfx(tIn0, "whoosh", { gain: 0.1 }); c.sfx(tIn0, "riser", { dur: tc - tIn0, gain: 0.12 });
      tl.fromTo(c.sel(`.or-r${i}`), { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.4, ease: "power2.out", immediateRender: false }, tc);
      tl.fromTo(c.sel(".or-ring"), { scale: 0.2, opacity: 1, x: E.x - OR.cx, y: E.y - OR.cy }, { scale: 6, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, tc);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-12, 6], [10, -6], [-6, 3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.06 })), immediateRender: false }, tc);
      tl.fromTo(c.sel(".or-centre"), { scale: 1 }, { scale: 1.07, duration: 0.25, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tc);
      c.particles("burst", tc - 0.05, tc + 1.6, { at: tc, x: E.x, y: E.y, spread: 3.1, g: 0, count: 90, seed: 53, color: c.L.particles.accent });
      c.sfx(tc, "impact", { gain: 0.16 }); c.sfx(tc + 0.05, "chime", { step: 2, gain: 0.1 });
    } else {
      const t = Math.max(...tIn.slice(0, n)) + 0.7;
      tl.fromTo(c.sel(".or-ring"), { scale: 0.3, opacity: 1 }, { scale: 6.5, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      c.sfx(t, "chime", { step: 3, gain: 0.09 });
    }
    if (p.result) c.rise(".or-result", p.resultAt ? c.at(p.resultAt) : p.passer ? tc + 0.8 : Math.max(...tIn.slice(0, n)) + 1.2, { ease: "power4.out" });
  },
});
