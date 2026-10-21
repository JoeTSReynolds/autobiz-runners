// Photo dive: a real photo with a marked area, a crossfade to its x-ray, a scan line, a lock box with a tag
// on one part, then a zoom-through that ends exactly where the next part starts (so the next part's `at`
// sets the dive). The lock tag must stay readable for 0.9 s before the zoom, or the build fails. Points are image coordinates (0..1) on `photo`;
// `focus` is the image point that sits at (540, 380) on screen.
BP.define("chip-dive", {
  photo: true, // a photo sits behind the caption band
  ground: "dark",
  slots: {
    photo: { type: "image" }, xray: { type: "image" }, focus: { type: "point" },
    mark: { type: "object", of: { a: { type: "point" }, b: { type: "point" } } },
    lock: { type: "object", of: { a: { type: "point" }, b: { type: "point" }, tag: { type: "text", max: 30 }, at: { type: "anchor" } } },
    xrayAt: { type: "anchor" }, scanAt: { type: "anchor" },
  },
  html(p) {
    const m = kit.cover(p.photo, 1920, 1920), [fx, fy] = m.px(p.focus), L = 540 - fx, T = 380 - fy; // the 1920 px square's corner
    const img = (n, cls, op) => { const k = kit.cover(n, 1920, 1920); return `<img class="${cls}" src="assets/${n}" style="position:absolute;left:${L + k.ox}px;top:${T + k.oy}px;width:${k.iw}px;height:${k.ih}px;opacity:${op}" />`; };
    const [x0, y0] = m.px(p.lock.a), [x1, y1] = m.px(p.lock.b);
    const box = (a, b, cls, bw) => { const [ax, ay] = m.px(a), [bx, by] = m.px(b); return `<div class="${cls}" style="position:absolute;left:${L + ax}px;top:${T + ay}px;width:${bx - ax}px;height:${by - ay}px;border:${bw}px solid var(--accent);opacity:0"></div>`; };
    return `${img(p.photo, "cd-photo", 1)}${img(p.xray, "cd-xray", 0)}${box(p.mark.a, p.mark.b, "cd-mark", 8)}
      <div class="cd-scan" style="position:absolute;left:0;right:0;top:0;height:10px;background-color:var(--accent);opacity:0"></div>
      ${box(p.lock.a, p.lock.b, "cd-lock", 10)}
      <div class="lbl cd-tag" style="position:absolute;left:${L + x0}px;top:${T + y1 + 20}px;background-color:var(--accent);color:var(--ink);padding:14px 22px;opacity:0">${p.lock.tag}</div>`;
  },
  animate(c) {
    const { tl, p } = c, dive = c.next, [photo, xray, mark, lock, tag, scan] = ["photo", "xray", "mark", "lock", "tag", "scan"].map((k) => c.q(".cd-" + k));
    // a slow push-in towards the focus point, until the zoom-through takes over
    [photo, xray].forEach((e) => tl.fromTo(e, { scale: 1 }, { scale: 1.12, duration: dive - c.start, ease: "none", transformOrigin: `${540 - parseFloat(e.style.left)}px ${380 - parseFloat(e.style.top)}px`, data: "ambient" }, c.start));
    tl.fromTo(mark, { opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, duration: 0.35, ease: "expo.out", transformOrigin: "left center" }, c.start + 0.25);
    c.sfx(c.start + 0.25, "click", { f0: 1200 });
    const xr = c.at(p.xrayAt);
    tl.to(mark, { opacity: 0, duration: 0.2 }, Math.max(xr, c.start + 0.6)); // never before its own entrance ends
    tl.to(xray, { opacity: 1, duration: 0.5, ease: "power2.inOut" }, xr);
    c.sfx(xr, "whoosh", { dur: 0.5, f0: 1600, f1: 400 });
    const sc = c.at(p.scanAt);
    tl.fromTo(scan, { y: 0, opacity: 1 }, { y: 1900, duration: 0.9, ease: "none" }, sc);
    tl.to(scan, { opacity: 0, duration: 0.1 }, sc + 0.9);
    c.sfx(sc, "scratch", { dur: 0.9 });
    const lk = c.at(p.lock.at);
    if (dive - 0.7 - (lk + 0.45) < 0.9) throw new Error(`chip-dive in ${c.scene}: the "${p.lock.tag}" tag shows for ${(dive - 0.7 - lk - 0.45).toFixed(1)} s before the zoom; needs 0.9 s (lock earlier or start the next part later)`);
    tl.fromTo(lock, { opacity: 0, scale: 1.4 }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, lk);
    tl.fromTo(tag, { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.3, ease: "expo.out" }, lk + 0.15);
    c.sfx(lk, "pop", { step: 3 });
    // one local origin for all four, so the boxes sweep past while the photo rushes in
    tl.to([photo, xray, lock, tag], { scale: 4, duration: 0.7, ease: "power4.in", transformOrigin: "540px 380px" }, dive - 0.7);
    c.sfx(dive - 0.7, "whoosh-big", { dur: 0.8 });
  },
});
