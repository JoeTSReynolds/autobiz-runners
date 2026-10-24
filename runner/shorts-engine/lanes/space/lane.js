window.LANE = {
  id: "space",
  key: [146.83, 185.0, 220.0, 246.94, 293.66], // D major pentatonic: the pitch of the synth pops, blips and chimes
  music: "space", // a recorded track from sounds/music/space/, chosen per video
  colors: { dark: "#0b0b0b", light: "#f3f2ec", accent: "#e03c31", rock: "#c9c7bf", mid: "#77756f", ink: "#111111" },
  particles: { ambient: "stars", dust: "230,228,220", accent: "224,60,49" },
  font: '700 100px "Nimbus Sans"', // what the driver waits for before measuring text
  fonts: ["NimbusSans-Regular.otf", "NimbusSans-Bold.otf"],
};
// Lane motif: a flat geological cross-section (surface, pit skylight, suspected tube), drawn into an
// <svg viewBox="0 0 1080 860">. Dashed red = unconfirmed. Returns the parts blueprints animate.
LANE.crossSection = (svg) => {
  const NS = "http://www.w3.org/2000/svg", C = LANE.colors;
  const el = (tag, a, parent = svg) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); parent.appendChild(e); return e; };
  const TUBE = "M455 330 C 455 520, 300 560, 0 560 L0 700 C 380 700, 620 680, 1080 610 L1080 470 C 760 520, 600 470, 560 330";
  el("rect", { x: 0, y: 0, width: 1080, height: 860, fill: C.light });
  el("path", { d: "M0 170 L430 170 L455 330 L560 330 L585 170 L1080 170 L1080 860 L0 860 Z", fill: C.rock });
  el("path", { d: "M0 170 L430 170 L455 330 L560 330 L585 170 L1080 170", fill: "none", stroke: C.ink, "stroke-width": 6 });
  const tube = el("path", { d: TUBE, fill: "none", stroke: C.accent, "stroke-width": 7, "stroke-dasharray": "22 14", opacity: 0 });
  const mystery = el("g", { opacity: 0 });
  el("path", { d: TUBE + " Z", fill: C.ink }, mystery);
  const q = el("text", { x: 540, y: 690, "text-anchor": "middle", "font-family": "Nimbus Sans", "font-weight": 700, "font-size": 300, fill: C.accent }, mystery);
  q.textContent = "?";
  return { el, tube, mystery, q };
};
