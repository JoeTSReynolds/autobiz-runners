// Shared helpers for narrated Shorts. Needs window.TIMING (from tts_el.py) and gsap.
// Everything goes on one paused timeline, so HyperFrames can seek any frame.
window.kit = (() => {
  const T = window.TIMING;
  const holds = [], cues = [], meta = { key: [146.83, 220.0, 293.66, 369.99, 440.0], hero: null };
  const scene = (id) => {
    const s = T.scenes.find((s) => s.id === id);
    if (!s) throw new Error(`no scene "${id}" in timing`);
    return s;
  };
  const sceneAt = (t) => T.scenes.find((s) => t >= s.start && t < s.end) || T.scenes.at(-1);
  // Start time of the nth spoken word in a scene that begins with `text`; visuals lock to the voice.
  const W = (id, text, n = 0) => {
    const t = text.toLowerCase(), hits = scene(id).words.filter((w) => { const x = w.w.toLowerCase().replace(/^[$£€]/, ""); return x.startsWith(t) || x.split("-").some((part) => part.startsWith(t)); });
    if (!hits[n]) throw new Error(`word "${text}" #${n} not spoken in scene ${id}`);
    return hits[n].s;
  };
  // Scenes: hard cuts plus a slow camera drift on each.
  function scenes(tl, { cuts = true } = {}) {
    if (scenes.done) return;
    scenes.done = true;
    if (cuts) T.scenes.slice(1).forEach((s) => tl.set(document.getElementById(s.id), { autoAlpha: 0 }, 0));
    for (const s of T.scenes) {
      const el = document.getElementById(s.id);
      if (!el) throw new Error(`no element #${s.id} for scene`);
      if (cuts) tl.set(el, { autoAlpha: 1 }, s.start).set(el, { autoAlpha: 0 }, s.end);
      tl.fromTo(el, { scale: 1 }, { scale: 1.04, duration: s.end - s.start, ease: "none", transformOrigin: "50% 40%", data: "ambient" }, s.start);
    }
    if (cuts) tl.set(document.getElementById(T.scenes.at(-1).id), { autoAlpha: 1 }, T.duration - 0.01);
  }
  // Transitions at scene boundaries, on the #cam wrapper that holds every scene:
  // { toSceneId: [type, duration] }, type = "zoom" (zoom-through with blur and a barrel-lens stretch),
  // "glitch" (RGB split + jitter), "whip" (horizontal motion-blur pan) or "flash". Unlisted boundaries cut.
  // Built from SVG filters, so every frame is deterministic. Each transition gets its own sound.
  function transitions(tl, map) {
    scenes(tl);
    const cam = document.getElementById("cam");
    if (!cam) throw new Error("transitions need a #cam wrapper around the scenes");
    // barrel displacement map: pixels are pulled from further out the nearer they are to the edge
    const c = document.createElement("canvas"); c.width = 108; c.height = 192;
    const g = c.getContext("2d"), img = g.createImageData(108, 192);
    for (let y = 0; y < 192; y++) for (let x = 0; x < 108; x++) {
      const nx = x / 107.5 * 2 - 1, ny = y / 191.5 * 2 - 1, r2 = nx * nx + ny * ny, i = (y * 108 + x) * 4;
      img.data[i] = 128 + 127 * Math.max(-1, Math.min(1, nx * r2 * 0.5)); img.data[i + 1] = 128 + 127 * Math.max(-1, Math.min(1, ny * r2 * 0.5));
      img.data[i + 2] = 128; img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    const defs = document.createElement("div");
    defs.innerHTML = `<svg width="0" height="0" style="position:absolute"><defs>
      <filter id="fx-lens" x="0" y="0" width="1080" height="1920" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
        <feImage href="${c.toDataURL()}" x="0" y="0" width="1080" height="1920" preserveAspectRatio="none" result="map"/>
        <feDisplacementMap id="fx-disp" in="SourceGraphic" in2="map" scale="0" xChannelSelector="R" yChannelSelector="G" result="d"/>
        <feGaussianBlur id="fx-blur" in="d" stdDeviation="0"/></filter>
      <filter id="fx-rgb" x="0" y="0" width="1080" height="1920" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
        <feColorMatrix in="SourceGraphic" values="1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0" result="r"/>
        <feOffset id="fx-roff" in="r" dx="0" result="ro"/>
        <feColorMatrix in="SourceGraphic" values="0 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 1 0" result="gb"/>
        <feOffset id="fx-boff" in="gb" dx="0" result="gbo"/>
        <feBlend in="ro" in2="gbo" mode="screen"/></filter>
      <filter id="fx-whip" x="0" y="0" width="1080" height="1920" filterUnits="userSpaceOnUse"><feGaussianBlur id="fx-wblur" stdDeviation="0 0"/></filter>
    </defs></svg><div id="fx-flash" style="position:absolute;inset:0;background:#fff;opacity:0;z-index:25;pointer-events:none"></div>`;
    document.getElementById("root").appendChild(defs);
    const $id = (id) => document.getElementById(id);
    for (const [id, [type, d]] of Object.entries(map)) {
      const b = scene(id).start, a = b - d / 2, h = d / 2;
      if (type === "zoom") {
        tl.set(cam, { filter: "url(#fx-lens)" }, a).set(cam, { filter: "none" }, b + h);
        tl.fromTo(cam, { scale: 1 }, { scale: 1.45, duration: h, ease: "power3.in", immediateRender: false }, a)
          .fromTo(cam, { scale: 1.45 }, { scale: 1, duration: h, ease: "power3.out", immediateRender: false }, b);
        tl.fromTo($id("fx-disp"), { attr: { scale: 0 } }, { attr: { scale: 220 }, duration: h, ease: "power2.in", immediateRender: false }, a)
          .to($id("fx-disp"), { attr: { scale: 0 }, duration: h, ease: "power2.out" }, b);
        tl.fromTo($id("fx-blur"), { attr: { stdDeviation: 0 } }, { attr: { stdDeviation: 16 }, duration: h, ease: "power2.in", immediateRender: false }, a)
          .to($id("fx-blur"), { attr: { stdDeviation: 0 }, duration: h, ease: "power2.out" }, b);
        sfx(a, "whoosh-big", { dur: d + 0.2 });
      } else if (type === "glitch") {
        tl.set(cam, { filter: "url(#fx-rgb)" }, a).set(cam, { filter: "none" }, b + h);
        tl.to(cam, { keyframes: [-38, 26, -14, 44, -20, 0].map((x) => ({ x, duration: d / 6, ease: "steps(1)" })) }, a);
        tl.to($id("fx-roff"), { keyframes: [{ attr: { dx: 28 }, duration: h, ease: "steps(3)" }, { attr: { dx: 0 }, duration: h, ease: "steps(3)" }] }, a);
        tl.to($id("fx-boff"), { keyframes: [{ attr: { dx: -28 }, duration: h, ease: "steps(3)" }, { attr: { dx: 0 }, duration: h, ease: "steps(3)" }] }, a);
        for (let k = 0; k < 5; k++) sfx(a + (k * d) / 5, "click", { f0: 900 + k * 500, gain: 0.12 });
      } else if (type === "whip") {
        tl.set(cam, { filter: "url(#fx-whip)" }, a).set(cam, { filter: "none" }, b + h);
        tl.fromTo(cam, { x: 0 }, { x: -420, duration: h, ease: "power3.in", immediateRender: false }, a)
          .fromTo(cam, { x: 420 }, { x: 0, duration: h, ease: "power3.out", immediateRender: false }, b);
        tl.fromTo($id("fx-wblur"), { attr: { stdDeviation: "0 0" } }, { attr: { stdDeviation: "40 0" }, duration: h, ease: "power2.in", immediateRender: false }, a)
          .to($id("fx-wblur"), { attr: { stdDeviation: "0 0" }, duration: h, ease: "power2.out" }, b);
        sfx(a, "whoosh", { dur: d, f0: 400, f1: 3000, gain: 0.2 });
      } else if (type === "flash") {
        tl.fromTo($id("fx-flash"), { opacity: 0 }, { opacity: 1, duration: h, ease: "power2.in", immediateRender: false }, a)
          .to($id("fx-flash"), { opacity: 0, duration: h * 1.6, ease: "power2.out" }, b);
        sfx(b, "chime", { step: 4, gain: 0.1 });
      } else throw new Error(`unknown transition ${type}`);
    }
  }
  // Wrap each .line of `sel` in a mask so lines can rise into view. The mask is padded (and pulled back
  // by the same margin) so tall glyphs and tight display leading are never clipped.
  function lines(sel) {
    document.querySelectorAll(sel + " .line").forEach((l) => {
      if (l.parentElement.classList.contains("mask")) return;
      const m = document.createElement("div");
      m.className = "mask";
      Object.assign(m.style, { overflow: "hidden", padding: "0.2em 0.08em", margin: "-0.2em -0.08em" });
      l.parentNode.insertBefore(m, l);
      m.appendChild(l);
    });
    return document.querySelectorAll(sel + " .line");
  }
  // Reveal lines; records a reading hold (checked by pace) unless opts.hold === false.
  function rise(tl, sel, at, opts = {}) {
    const ls = lines(sel), dur = opts.duration || 0.8, st = opts.stagger ?? 0.09;
    if (opts.hold !== false && opts.min !== undefined) { // near miss on reading time: bring the reveal forward
      const words = [...ls].map((l) => l.textContent).join(" ").split(/\s+/).filter(Boolean).length;
      const end = opts.until ?? sceneAt(at).end, short = 1 + 0.25 * Math.max(0, words - 3) - (end - (at + dur * 0.6 + st * (ls.length - 1)));
      if (short > 0) at = Math.max(opts.min, at - short);
    }
    tl.fromTo(ls, { yPercent: 170 }, { yPercent: 0, duration: dur, ease: opts.ease || "expo.out", stagger: st }, at);
    if (opts.sound !== false) sfx(at, "whoosh", { gain: 0.07 });
    if (opts.hold !== false) {
      const words = [...ls].map((l) => l.textContent).join(" ").split(/\s+/).filter(Boolean).length;
      holds.push({ sel, at, settle: at + dur * 0.6 + st * (ls.length - 1), words, until: opts.until });
    }
  }
  function count(tl, el, from, to, at, dur, fmt) {
    const o = { v: from }, node = typeof el === "string" ? document.querySelector(el) : el;
    node.textContent = fmt(from);
    tl.to(o, { v: to, duration: dur, ease: "power3.out", onUpdate: () => (node.textContent = fmt(o.v)) }, at);
    for (let k = 0; k < 6; k++) sfx(at + (k * dur) / 8, "click", { gain: 0.05, f0: 1600 + k * 200 });
  }
  // Word-by-word captions in groups of up to `size`; a group ends at sentence punctuation or a pause
  // longer than `gap` s, so words never show before the voice reaches them. Numbers get class "num".
  function captions(tl, box, { size = 3, gap = 0.3, fix = {} } = {}) {
    for (const s of T.scenes) {
      const groups = [];
      for (const w of s.words) {
        const g = groups.at(-1), prev = g && g.at(-1);
        if (!g || g.length >= size || prev.p || w.s - prev.e > gap) groups.push([w]);
        else g.push(w);
      }
      for (let i = 0; i < groups.length; i++) {
        const g = groups[i], next = groups[i + 1] && groups[i + 1][0];
        const row = document.createElement("div");
        row.className = "cap";
        row.style.visibility = "hidden";
        g.forEach((w) => {
          const span = document.createElement("span");
          span.textContent = fix[w.w] || w.w;
          if (/\d/.test(w.w)) span.className = "num";
          row.appendChild(span);
        });
        box.appendChild(row);
        const end = Math.min(g.at(-1).e + 0.2, s.end, next ? next.s - 0.05 : Infinity); // never two groups on screen
        tl.set(row, { visibility: "visible" }, g[0].s - 0.04).set(row, { visibility: "hidden" }, end);
        g.forEach((w, k) => {
          const sp = row.children[k];
          tl.set(sp, { opacity: 1 }, w.s).set(sp, { opacity: 0.5 }, w.e + 0.08);
          if (sp.className === "num") tl.fromTo(sp, { scale: 1.35 }, { scale: 1, duration: 0.35, ease: "back.out(3)" }, w.s);
        });
      }
    }
  }
  // Sound cues for sfx_render.py: recorded at the same moments as the visuals, so sound can't drift.
  function sfx(t, type, opts = {}) { cues.push({ t: Math.max(0, +t.toFixed(3)), type, ...opts }); }
  function sound(o) { Object.assign(meta, o); }
  // The hero moment: a riser that lands exactly on it, an impact, and the music bed ducks.
  function hero(t, riser = 2.4) { meta.hero = t; sfx(t - riser, "riser", { dur: riser }); sfx(t, "impact"); }
  // A fresh full-frame particle canvas behind the content of `parentSel` (one per effect: effects clear their canvas).
  function canvas(parentSel) {
    const c = document.createElement("canvas");
    Object.assign(c, { width: 1080, height: 1920, className: "fx" });
    const p = document.querySelector(parentSel);
    p.insertBefore(c, p.firstChild);
    return c;
  }
  // Seeded particles on a canvas, drawn as a pure function of time between `from` and `to`.
  function particles(tl, canvas, kind, from, to, o = {}) {
    const ctx = canvas.getContext("2d"), w = canvas.width, h = canvas.height;
    let seed = o.seed || 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const ps = Array.from({ length: o.count || 140 }, () => ({ x: rnd() * w, y: rnd() * h, z: rnd(), a: rnd() * 6.283, s: rnd() }));
    const col = o.color || "255,255,255";
    const draw = (t) => {
      ctx.clearRect(0, 0, w, h);
      for (const p of ps) {
        if (kind === "stars") { // three depths drifting at different speeds, twinkling
          const x = (((p.x + t * (o.vx ?? -14) * (0.3 + p.z)) % w) + w) % w, y = (((p.y + t * (o.vy ?? 6) * (0.3 + p.z)) % h) + h) % h;
          ctx.fillStyle = `rgba(${col},${(0.25 + 0.75 * p.z) * (0.65 + 0.35 * Math.sin(t * (1 + 3 * p.s) + p.a))})`;
          ctx.fillRect(x, y, 1 + 2.6 * p.z, 1 + 2.6 * p.z);
        } else if (kind === "dust") { // soft motes floating up with a sway
          const y = (((p.y - t * (10 + 30 * p.z)) % h) + h) % h, x = p.x + Math.sin(t * 0.6 + p.a) * 24;
          ctx.fillStyle = `rgba(${col},${0.08 + 0.22 * p.z})`;
          ctx.beginPath(); ctx.arc(x, y, 2 + 6 * p.z, 0, 6.283); ctx.fill();
        } else if (kind === "sparks") { // fast streaks along x, like data on a bus
          const x = (((p.x + t * (300 + 900 * p.s)) % (w + 400)) + w + 400) % (w + 400) - 200, len = 40 + 160 * p.s;
          ctx.fillStyle = `rgba(${col},${0.25 + 0.6 * p.z})`;
          ctx.fillRect(x - len, Math.round(p.y / 24) * 24, len, 2 + 3 * p.z);
        } else if (kind === "burst") { // one explosion at o.x,o.y: fling, gravity, fade
          const age = t - (o.at - from);
          if (age < 0 || age > 1.6) continue;
          const ang = (o.dir ?? -Math.PI / 2) + (p.a - 3.14) * (o.spread ?? 0.9), v = 250 + 900 * p.s;
          const x = o.x + Math.cos(ang) * v * age, y = o.y + Math.sin(ang) * v * age + 0.5 * (o.g ?? 900) * age * age;
          ctx.fillStyle = `rgba(${col},${Math.max(0, 1 - age / 1.6) * (0.4 + 0.6 * p.z)})`;
          ctx.fillRect(x, y, 2 + 5 * p.z, 2 + 5 * p.z);
        }
      }
    };
    tl.set(canvas, { visibility: "visible" }, from).set(canvas, { visibility: "hidden" }, to);
    tl.to({}, { duration: to - from, ease: "none", data: "ambient", onUpdate() { draw(this.time()); } }, from);
  }
  function spansOf(tl) {
    return tl.getChildren(true, true, false)
      .filter((c) => c.data !== "ambient")
      .filter((c) => { const t = c.targets()[0]; return !(t instanceof Element && (t.closest("#caps") || t.id === "grain")); })
      .map((c) => [c.startTime(), c.startTime() + c.totalDuration()]).sort((a, b) => a[0] - b[0]);
  }
  // The smaller motion between big beats: a gentle camera breath (and a soft tick) on a word mid-gap.
  function fillQuiet(tl, maxGap) {
    const cam = document.getElementById("cam");
    if (!cam) return;
    let covered = 0;
    for (const [s, e] of spansOf(tl).concat([[T.duration - 1.5, T.duration - 1.5]]).filter(([s]) => s <= T.duration - 1.5)) {
      for (let from = covered; s - from > maxGap; ) {
        const w = T.scenes.flatMap((x) => x.words).filter((w) => w.s > from + 1.2 && w.s < Math.min(s - 0.4, from + maxGap - 0.2)).at(-1);
        if (!w) break; // a silent gap: left for pace() to report
        tl.fromTo(cam, { scale: 1 }, { scale: 1.025, duration: 0.35, ease: "power2.out", yoyo: true, repeat: 1, transformOrigin: "50% 45%", immediateRender: false }, w.s);
        sfx(w.s, "click", { gain: 0.04, f0: 2600 });
        from = w.s + 0.7;
      }
      covered = Math.max(covered, e);
    }
  }
  // Retention checks (throw, so a slow or unreadable video fails the build instead of shipping):
  // 1. a visible change at least every `maxGap` s (ambient drifts, captions and grain don't count);
  // 2. every revealed text holds >= 1 s + 0.25 s per word over three, before its scene (or opts.until) ends.
  function pace(tl, maxGap = 3) {
    fillQuiet(tl, maxGap);
    const spans = tl.getChildren(true, true, false)
      .filter((c) => c.data !== "ambient")
      .filter((c) => { const t = c.targets()[0]; return !(t instanceof Element && (t.closest("#caps") || t.id === "grain")); })
      .map((c) => [c.startTime(), c.startTime() + c.totalDuration()])
      .concat([[T.duration - 1.5, T.duration - 1.5]]) // the last 1.5 s is the end card: allowed to sit still
      .sort((a, b) => a[0] - b[0]);
    const bad = [];
    let covered = 0;
    for (const [s, e] of spans.filter(([s]) => s <= T.duration - 1.5)) {
      if (s - covered > maxGap) { // name the scene and the words spoken in the gap, so a model can anchor a beat there
        const sc = sceneAt(covered + 0.01), ws = T.scenes.flatMap((x) => x.words.map((w) => ({ ...w, id: x.id }))).filter((w) => w.s > covered + 0.3 && w.s < s - 0.3);
        bad.push(`scene "${sc.id}": nothing changes ${covered.toFixed(1)}–${s.toFixed(1)}s; anchor a visual beat to a word spoken in that gap (${ws.map((w) => `"${w.w.toLowerCase()}"@${w.s.toFixed(1)} in ${w.id}`).join(", ") || "no words: shorten the pause"})`);
      }
      covered = Math.max(covered, e);
    }
    for (const h of holds) {
      const end = h.until ?? sceneAt(h.at).end, need = 1 + 0.25 * Math.max(0, h.words - 3);
      if (end - h.settle < need - 0.05) bad.push(`${h.sel} readable for ${(end - h.settle).toFixed(1)}s, needs ${need.toFixed(1)}s`);
    }
    if (bad.length) throw new Error("pacing: " + bad.join("; "));
    window.SFX = { duration: T.duration, ...meta, cues: cues.sort((a, b) => a.t - b.t) };
  }
  // Where an image point lands when the image covers a w x h box (centred): px(pt) -> [x, y] in the box.
  function cover(name, w, h) {
    const d = (window.IMAGES || {})[name];
    if (!d) throw new Error(`image ${name}: size unknown (not in storyboard params?)`);
    const k = Math.max(w / d[0], h / d[1]), iw = d[0] * k, ih = d[1] * k, ox = (w - iw) / 2, oy = (h - ih) / 2;
    return { iw, ih, ox, oy, px: (pt) => [ox + pt.x * iw, oy + pt.y * ih] };
  }
  return { T, scene, W, cover, scenes, transitions, lines, rise, count, captions, sfx, sound, hero, canvas, particles, pace, S: (id) => scene(id).start, E: (id) => scene(id).end };
})();

// Blueprint registry. A blueprint = { slots, ground, overlay?, html(p, c), animate(c) }; see driver.js.
// Slots validate storyboard params so a bad storyboard fails with every error listed, never a broken frame.
window.BP = (() => {
  const all = {};
  function check(slots, p, path, errs) {
    if (typeof p !== "object" || p === null || Array.isArray(p)) return errs.push(`${path}: expected an object`);
    for (const k of Object.keys(p)) if (!slots[k]) errs.push(`${path}.${k}: not a slot (slots: ${Object.keys(slots).join(", ")})`);
    for (const [k, s] of Object.entries(slots)) {
      const v = p[k], at = `${path}.${k}`;
      if (v === undefined) { if (!s.opt) errs.push(`${at}: required`); continue; }
      const t = s.type;
      if (t === "text" || t === "anchor" || t === "image") {
        if (typeof v !== "string" || !v) errs.push(`${at}: expected a non-empty string`);
        else if (s.max && v.length > s.max) errs.push(`${at}: "${v}" is ${v.length} chars, max ${s.max}`);
      } else if (t === "lines") {
        if (!Array.isArray(v) || !v.length || v.some((l) => typeof l !== "string" || !l)) errs.push(`${at}: expected an array of non-empty strings, one per line`);
        else {
          if (v.length > s.lines) errs.push(`${at}: ${v.length} lines, max ${s.lines}`);
          v.forEach((l, i) => l.length > s.max && errs.push(`${at}[${i}]: "${l}" is ${l.length} chars, max ${s.max} per line`));
        }
      } else if (t === "number") {
        if (typeof v !== "number" || !isFinite(v)) errs.push(`${at}: expected a number`);
        else if ((s.min !== undefined && v < s.min) || (s.max !== undefined && v > s.max)) errs.push(`${at}: ${v} outside ${s.min}..${s.max}`);
      } else if (t === "bool") { if (typeof v !== "boolean") errs.push(`${at}: expected true or false`); }
      else if (t === "enum") { if (!s.values.includes(v)) errs.push(`${at}: "${v}" is not one of ${s.values.join(", ")}`); }
      else if (t === "point") {
        if (!v || [v.x, v.y].some((n) => typeof n !== "number" || n < 0 || n > 1)) errs.push(`${at}: expected {x, y} between 0 and 1`);
      } else if (t === "object") {
        check(s.of, v, at, errs);
      } else if (t === "list") {
        if (!Array.isArray(v)) errs.push(`${at}: expected a list`);
        else {
          if (v.length < (s.min || 0) || v.length > (s.max || 99)) errs.push(`${at}: ${v.length} items, need ${s.min || 0}..${s.max || 99}`);
          v.forEach((item, i) => check(s.of, item, `${at}[${i}]`, errs));
        }
      } else errs.push(`${at}: blueprint declares unknown slot type ${t}`);
    }
    return errs;
  }
  return {
    define(name, def) { all[name] = def; },
    get(name) { return all[name]; },
    names: () => Object.keys(all),
    check,
    // shared shape for line-swing / line-flat: ~1.5 cycles across 936 x 480, top 20, bottom 460
    swingPoints() { const pts = []; for (let x = 0; x <= 936; x += 6) pts.push(`${x},${(240 - Math.sin((x / 936) * Math.PI * 3) * 220).toFixed(1)}`); return pts.join(" "); },
  };
})();
