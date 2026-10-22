// Builds a Short from window.STORYBOARD + window.TIMING + window.LANE using the BP registry.
// storyboard: { title, credit, scenes: [{ id, say, transition?, parts: [{ blueprint, at?, params }] }] }
// Part 0 starts with its scene; part n starts at the spoken word `at` ("word" or "word#2" for the 3rd one).
window.buildShort = () => {
  const SB = window.STORYBOARD, L = window.LANE, T = kit.T;
  const errs = [];
  if (T.scenes.map((s) => s.id).join() !== SB.scenes.map((s) => s.id).join()) errs.push("storyboard scenes do not match the narration timing; re-run the voiceover");
  const anchor = (sceneId, a) => { const [w, n] = String(a).split("#"); return kit.W(sceneId, w, +(n || 0)); };
  const built = [];
  for (const sc of SB.scenes) {
    if (!Array.isArray(sc.parts) || !sc.parts.length) { errs.push(`scenes.${sc.id}: needs at least one part`); continue; }
    sc.parts.forEach((p, i) => {
      const bp = BP.get(p.blueprint), path = `scenes.${sc.id}.parts[${i}]`;
      if (!bp) return errs.push(`${path}: unknown blueprint "${p.blueprint}" (have: ${BP.names().join(", ")})`);
      if (i > 0 && !p.at) errs.push(`${path}: needs "at", the spoken word where it starts`);
      BP.check(bp.slots, p.params || {}, `${path}.params`, errs);
      if (bp.validate && p.params) for (const e of bp.validate(p.params)) errs.push(`${path}.params: ${e}`);
      for (const [k, s] of Object.entries(bp.slots)) if (s.type === "anchor" && p.params?.[k]) { try { anchor(sc.id, p.params[k]); } catch (e) { errs.push(`${path}.params.${k}: ${e.message}`); } }
      built.push({ sc, p, i, bp });
    });
  }
  if (errs.length) throw new Error("storyboard: " + errs.join("; "));

  document.getElementById("root").dataset.duration = T.duration; // length comes from the narration
  const tl = gsap.timeline({ paused: true }), cam = document.getElementById("cam");
  kit.sound({ key: L.key, music: L.music });
  for (const sc of SB.scenes) { const sec = document.createElement("section"); sec.className = "scene"; sec.id = sc.id; cam.appendChild(sec); }
  const dur = { zoom: 0.8, glitch: 0.5, whip: 0.6 };
  // "flash" veils the new scene's text in white, which always fails the contrast audit: older storyboards get a zoom
  const kind = (t) => (t === "flash" ? "zoom" : t);
  kit.transitions(tl, Object.fromEntries(SB.scenes.filter((s) => s.transition).map((s) => [s.id, [kind(s.transition), dur[kind(s.transition)] || 0.7]])));
  // captions follow the ground under them; data-ground lets numbers avoid accent-on-accent
  // photo: a photo sits behind the caption band, so captions get a backing plate to stay readable
  const groundAt = (t, g, photo = false) => tl.set("#caps", { color: g === "dark" ? L.colors.light : L.colors.ink, attr: { "data-ground": g, "data-photo": photo ? 1 : 0 } }, t);

  // build every part's DOM first (scenes are created empty by the template)
  for (const b of built) {
    const s = kit.scene(b.sc.id), parts = b.sc.parts, next = parts[b.i + 1];
    b.start = b.i === 0 ? s.start : anchor(b.sc.id, b.p.at);
    const nextStart = next ? anchor(b.sc.id, next.at) : s.end;
    const nbp = next && BP.get(next.blueprint);
    // an overlay lands on top of this part; one that covers the whole frame hides it once it is fully in
    b.end = nbp?.overlay ? (nbp.covers ? nextStart + nbp.covers : s.end) : nextStart;
    b.box = document.createElement("div");
    b.box.id = `${b.sc.id}-${b.i}`;
    b.ground = typeof b.bp.ground === "function" ? b.bp.ground(b.p.params || {}) : b.bp.ground || "dark";
    b.box.className = b.bp.overlay ? "part" : `part g-${b.ground}`; // overlays paint only their own content
    document.getElementById(b.sc.id).appendChild(b.box);
    const p = b.p.params || {}, sel = (x) => `#${b.box.id} ${x}`;
    b.c = {
      tl, p, L, box: b.box, start: b.start, end: b.end, next: nextStart, sceneStart: s.start, sceneEnd: s.end, scene: b.sc.id,
      at: (a) => anchor(b.sc.id, a),
      q: (x) => b.box.querySelector(x), qa: (x) => b.box.querySelectorAll(x), sel,
      rise: (x, t, o = {}) => kit.rise(tl, sel(x), t, { until: b.end, min: b.start + 0.05, ...o }),
      lines: (x) => kit.lines(sel(x)),
      count: (x, ...a) => kit.count(tl, b.box.querySelector(x), ...a),
      particles: (kind, from, to, o) => kit.particles(tl, kit.canvas("#" + b.box.id), kind, from, to, o),
      sfx: kit.sfx, hero: kit.hero, ground: (t, g) => groundAt(t, g),
    };
    b.box.innerHTML = b.bp.html(p, b.c);
  }
  // part visibility and caption colour follow the part on screen
  for (const b of built) {
    if (b.i > 0) tl.set(b.box, { autoAlpha: 0 }, 0).set(b.box, { autoAlpha: 1 }, b.start);
    if (b.end < b.c.sceneEnd) tl.set(b.box, { autoAlpha: 0 }, b.end);
    groundAt(b.start, b.ground, typeof b.bp.photo === "function" ? !!b.bp.photo(b.p.params || {}) : !!b.bp.photo);
  }
  // Display text never wraps: a line wider than its column shrinks (whole block) until the widest line fits.
  document.querySelectorAll("#cam .pad.d").forEach((el) => {
    const ls = el.querySelectorAll(".line").length ? [...el.querySelectorAll(".line")] : [el];
    ls.forEach((l) => (l.style.whiteSpace = "nowrap"));
    const widest = Math.max(...ls.map((l) => l.scrollWidth)), room = el.clientWidth;
    if (widest > room) el.style.fontSize = Math.floor(parseFloat(getComputedStyle(el).fontSize) * room / widest) + "px";
  });
  // any element with data-fitw="<px>" shrinks to fit that width (bar figures, tags)
  document.querySelectorAll("#cam [data-fitw]").forEach((el) => {
    const room = +el.dataset.fitw;
    if (el.scrollWidth > room) el.style.fontSize = Math.floor(parseFloat(getComputedStyle(el).fontSize) * room / el.scrollWidth) + "px";
  });
  for (const b of built) b.bp.animate(b.c);
  kit.captions(tl, document.getElementById("caps"));
  tl.to("#grain", { backgroundPosition: "256px 512px", duration: T.duration, ease: `steps(${Math.round(T.duration * 12)})` }, 0);
  tl.to({}, { duration: 0.01 }, T.duration - 0.01);
  kit.pace(tl, 3);
  return tl;
};
