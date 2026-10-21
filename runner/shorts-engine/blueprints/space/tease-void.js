// Open loop (space): a cross-section panel slides over the scene with an unknown void and a red "?".
// The reveal blueprint (xsec-reveal) resolves the same void later. Captions move up out of its way.
BP.define("tease-void", {
  overlay: true,
  ground: "dark", // captions sit over the photo above the panel
  slots: { qAt: { type: "anchor" }, shakeAt: { type: "anchor", opt: true } },
  html: () => `<svg class="tv" style="position:absolute;left:0;top:1060px" width="1080" height="760" viewBox="0 100 1080 760"></svg>`,
  animate(c) {
    const { tl, p } = c, xs = LANE.crossSection(c.q(".tv")), panel = c.sel(".tv");
    tl.fromTo(panel, { yPercent: 100 }, { yPercent: 0, duration: 0.6, ease: "expo.out" }, c.start);
    c.sfx(c.start, "whoosh", { dur: 0.5, f0: 300, f1: 1200 });
    tl.set("#caps", { top: 800 }, c.start).set("#caps", { top: 1470 }, c.sceneEnd);
    const q = c.at(p.qAt);
    tl.to(xs.mystery, { opacity: 1, duration: 0.4 }, q);
    tl.fromTo(xs.q, { scale: 0.4, transformOrigin: "540px 600px" }, { scale: 1, duration: 0.5, ease: "back.out(3)" }, q);
    c.sfx(q, "pop", { step: 4 });
    if (p.shakeAt) tl.fromTo(xs.q, { rotation: -6 }, { rotation: 6, duration: 0.18, repeat: 5, yoyo: true, ease: "sine.inOut", transformOrigin: "540px 600px" }, c.at(p.shakeAt));
    tl.to(panel, { yPercent: 100, duration: 0.4, ease: "power3.in" }, c.sceneEnd - 1.3);
  },
});
