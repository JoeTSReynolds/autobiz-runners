// A chat between two parties, `a` (left) and `b` (right), each message a hard-edged bubble that pops in and types
// itself on its own word (`from` says who speaks, `at` the word). At most one message can be `hidden`: it first
// sits blacked out (redacted), then on its `at` word the black bars glitch apart and the text types in with an
// accent outline, a shake and a burst. That is the hero beat; without one the last message is. Give `a` and `b`
// a `name`. Keep messages short (max 60 chars, 2..5 of them; they must all fit above the captions).
// Cast anything: a chatbot with a hidden system prompt (a label "You", b asset robot "Chatbot"; the hidden
// message is "Never reveal these rules"), mission control talking to a rover (a asset person or tower, b asset
// lander; hidden: the rover's secret finding), a customer and a support bot, two traders with a hidden order.
const EXC = { gap: 24, per: 24, end: 1400 };
EXC.h = (t) => Math.ceil(t.length / EXC.per) * 66 + 48;
BP.define("exchange", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    a: { type: "actor" }, b: { type: "actor" },
    messages: { type: "list", min: 2, max: 5, of: { from: { type: "enum", values: ["a", "b"] }, text: { type: "text", max: 60 }, at: { type: "anchor" }, hidden: { type: "bool", opt: true }, redactAt: { type: "anchor", opt: true } } },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  validate(p) {
    const m = p.messages || [], e = [], room = EXC.end - (p.head ? 705 : 585) - (p.result ? 100 : 0), need = m.reduce((s, x) => s + EXC.h(x.text) + EXC.gap, -EXC.gap);
    if (m.filter((x) => x.hidden).length > 1) e.push("at most one hidden message");
    if (need > room) e.push(`the messages need about ${need}px but only ${room}px fit; shorten them or use fewer`);
    return e;
  },
  html(p) {
    const avY = p.head ? 520 : 400, light = p.ground === "light";
    const bub = (m, i) => { const bg = m.from === "b" ? "var(--accent)" : light ? "var(--ink)" : "var(--light)", fg = m.from === "b" ? "var(--ink)" : light ? "var(--light)" : "var(--dark)";
      const words = m.text.split(" ").map((w) => `<span style="white-space:nowrap">${[...w].map((ch) => `<span class="ex-c" style="opacity:0">${ch}</span>`).join("")}</span>`).join(" ");
      return `<div class="t ex-b ex-b${i}" style="position:absolute;${m.from === "b" ? "right" : "left"}:72px;top:0;width:max-content;max-width:800px;padding:24px 30px;font-size:54px;line-height:1.2;background-color:${bg};color:${fg};opacity:0">${words}${m.hidden ? `<i class="ex-red" style="position:absolute;inset:12px 0;background-color:var(--ink)"></i>` : ""}</div>`; };
    return `${p.head ? `<div class="pad d ex-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      ${ACT.html(p.a, 170, "ex-av ex-av0", 157, avY)}${ACT.html(p.b, 170, "ex-av ex-av1", 923, avY)}
      ${p.messages.map(bub).join("")}
      ${p.result ? `<div class="pad d ex-result" style="top:1325px;font-size:96px;color:var(--accent-text)"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, ms = p.messages.map((m, i) => ({ ...m, i, t: c.at(m.at) })), top = (p.head ? 520 : 400) + 185, hs = ms.map((m) => c.q(`.ex-b${m.i}`).offsetHeight);
    const room = EXC.end - top - (p.result ? 100 : 0), gap = Math.min(110, Math.max(EXC.gap, (room - hs.reduce((a, b) => a + b, 0)) / Math.max(1, ms.length - 1))); // spread to fill the stage
    let y = top, prev = c.start + 0.4;
    ms.forEach((m, k) => { // stack the bubbles in order; each shows 0.2 s before its word (a hidden one earlier, still blacked out)
      const el = c.q(`.ex-b${m.i}`); el.style.top = y + "px"; y += hs[k] + gap;
      m.show = m.hidden ? Math.max(c.start + 0.5, Math.min(m.redactAt ? c.at(m.redactAt) : prev + 1.0, m.t - 0.8)) : Math.max(c.start + 0.5, m.t - 0.2);
      prev = m.show;
    });
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 41, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".ex-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    [0, 1].forEach((i) => tl.fromTo(c.sel(`.ex-av${i}`), { scale: 0.5, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "back.out(1.7)" }, c.start + 0.05 + i * 0.2));
    c.sfx(c.start + 0.05, "pop", { step: 0 }); c.sfx(c.start + 0.25, "pop", { step: 2 });
    ms.forEach((m, k) => {
      const B = c.sel(`.ex-b${m.i}`), chars = c.qa(`.ex-b${m.i} .ex-c`), dur = Math.min(1.4, 0.03 * m.text.length), origin = m.from === "b" ? "100% 50%" : "0% 50%";
      tl.fromTo(B, { autoAlpha: 0, scaleX: 0.6, transformOrigin: origin }, { autoAlpha: 1, scaleX: 1, duration: 0.3, ease: "back.out(2)" }, m.show);
      c.sfx(m.show, "pop", { step: m.from === "b" ? 3 : 1, dur: 0.12 });
      tl.fromTo(c.sel(`.ex-av${m.from === "b" ? 1 : 0} .act-v`), { scale: 1 }, { scale: 1.15, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false, transformOrigin: "50% 50%" }, m.show);
      tl.to(chars, { opacity: 1, duration: 0.01, stagger: dur / chars.length }, m.t);
      for (let j = 0; j < Math.min(6, Math.floor(m.text.length / 5)); j++) c.sfx(m.t + (j * dur) / 6, "click", { f0: 1500 + (m.from === "b" ? 700 : 0) + j * 120, gain: 0.06 });
      if (m.hidden) {
        const R = c.sel(`.ex-b${m.i} .ex-red`), cut = ["inset(0 0 0 0)", "inset(0 45% 0 0)", "inset(0 0 55% 0)", "inset(35% 0 0 60%)", "inset(0 0 0 25%)", "inset(60% 70% 0 0)"];
        c.sfx(m.show + 0.1, "blip", { step: 0, dur: 0.5, gain: 0.1 });
        tl.fromTo(R, { x: 0 }, { keyframes: cut.map((cp, j) => ({ x: [-18, 22, -10, 14, -8, 0][j], clipPath: cp, duration: 0.06, ease: "steps(1)" })), immediateRender: false }, m.t - 0.1);
        tl.set(R, { autoAlpha: 0 }, m.t + 0.26);
        tl.set(c.sel(`.ex-b${m.i}`), { outline: "6px solid var(--accent)", outlineOffset: "6px" }, m.t - 0.1);
        c.sfx(m.t - 0.1, "scratch", { dur: 0.4, gain: 0.14 }); c.sfx(m.t, "impact", { gain: 0.16 }); c.sfx(m.t + 0.1, "chime", { step: 3, gain: 0.1 });
        const el = c.q(`.ex-b${m.i}`), cy = parseFloat(el.style.top) + el.offsetHeight / 2;
        c.particles("burst", m.t - 0.05, m.t + 1.7, { at: m.t, x: m.from === "b" ? 1008 - el.offsetWidth / 2 : 72 + el.offsetWidth / 2, y: cy, spread: 3.1, g: 400, count: 120, seed: 111, color: c.L.particles.accent });
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 6], [12, -8], [-6, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, m.t);
      }
    });
    const hero = ms.find((m) => m.hidden) || ms.at(-1);
    if (!hero.hidden) { c.sfx(hero.t, "impact", { gain: 0.12 }); c.sfx(hero.t + 0.1, "chime", { step: 2, gain: 0.09 }); }
    if (p.result) c.rise(".ex-result", p.resultAt ? c.at(p.resultAt) : hero.t + 1.2, { ease: "power4.out" });
  },
});
