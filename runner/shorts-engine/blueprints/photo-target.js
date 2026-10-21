// A real photo with a ring drawing onto one point of it, a two-line headline, optional dive into the point.
BP.define("photo-target", {
  photo: true, // a photo sits behind the caption band
  ground: "dark",
  slots: {
    headline: { type: "lines", max: 16, lines: 2 },
    image: { type: "image" },
    target: { type: "point" },           // in image coordinates (0..1)
    ringAt: { type: "anchor" },
    dive: { type: "bool", opt: true },   // zoom into the target as the scene ends
  },
  html(p) {
    const [tx, ty] = kit.cover(p.image, 1200, 1200).px(p.target);
    return `<div class="tgt-cam" style="position:absolute;left:${216 - tx}px;top:470px;width:1200px;height:1200px">
      <img src="assets/${p.image}" style="width:100%;height:100%;object-fit:cover;display:block" />
      <svg style="position:absolute;left:0;top:0" width="1200" height="1200"><circle class="tgt-ring" cx="${tx}" cy="${ty}" r="46" fill="none" stroke="var(--accent)" stroke-width="8" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>
    </div>
    <div class="pad d tgt-head" style="top:150px;font-size:150px">${p.headline.map((l) => `<div class="line">${l}</div>`).join("")}</div>`;
  },
  animate(c) {
    const { tl, p } = c, [tx, ty] = kit.cover(p.image, 1200, 1200).px(p.target), o = `${tx}px ${ty}px`, cam = c.sel(".tgt-cam");
    c.particles("stars", c.start, c.sceneEnd, { count: 220, seed: 3 });
    const driftEnd = p.dive ? c.sceneEnd - 1.1 : c.sceneEnd;
    tl.fromTo(cam, { scale: 0.92, rotation: -4 }, { scale: 1, rotation: 0, duration: driftEnd - c.start, ease: "none", transformOrigin: o, data: "ambient" }, c.start);
    c.rise(".tgt-head", c.start + 0.25, { stagger: 0.14, duration: 1.0, until: c.sceneEnd });
    const r = c.at(p.ringAt);
    tl.to(c.sel(".tgt-ring"), { attr: { "stroke-dashoffset": 0 }, duration: 0.7, ease: "power2.inOut" }, r);
    c.sfx(r, "scratch", { dur: 0.7 });
    tl.fromTo(c.sel(".tgt-ring"), { attr: { r: 46 } }, { attr: { r: 58 }, duration: 0.4, yoyo: true, repeat: 3, ease: "sine.inOut" }, r + 0.8);
    if (p.dive) tl.to(cam, { scale: 9, duration: 1.1, ease: "power4.in", transformOrigin: o }, c.sceneEnd - 1.1);
  },
});
