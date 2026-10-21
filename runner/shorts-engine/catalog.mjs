// Print the blueprint catalogue (what each is for + its slots) for a lane, straight from the code,
// so the storyboard-writing prompt can never drift from what the compiler accepts.
// Usage: node catalog.mjs <lane>
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const lane = process.argv[2], here = path.dirname(new URL(import.meta.url).pathname), defs = [];
const ctx = { BP: { define: (name, def) => defs.push({ name, def }) }, window: {} };
vm.createContext(ctx);
const files = [path.join(here, "blueprints"), path.join(here, "blueprints", lane)]
  .filter((d) => fs.existsSync(d))
  .flatMap((d) => fs.readdirSync(d).filter((f) => f.endsWith(".js")).map((f) => path.join(d, f)));
const about = {};
for (const f of files) {
  const src = fs.readFileSync(f, "utf8");
  vm.runInContext(src, ctx, { filename: f });
  const head = []; // only the file's leading comment block describes the blueprint
  for (const l of src.split("\n")) { if (!l.startsWith("//")) break; head.push(l.slice(3)); }
  about[defs.at(-1)?.name] = head.join(" ");
}
const fmt = (s) => {
  const o = s.opt ? " (optional)" : "";
  if (s.type === "lines") return `lines: up to ${s.lines} line(s), max ${s.max} chars each${o}`;
  if (s.type === "text") return `text, max ${s.max} chars${o}`;
  if (s.type === "number") return `number ${s.min ?? ""}..${s.max ?? ""}${o}`;
  if (s.type === "enum") return `one of ${s.values.join(" | ")}${o}`;
  if (s.type === "anchor") return `anchor${o}`;
  if (s.type === "point") return `point {x, y} in image coordinates 0..1${o}`;
  if (s.type === "image") return `image file name${o}`;
  if (s.type === "object") return `object${o}: { ${Object.entries(s.of).map(([k, v]) => `${k}: ${fmt(v)}`).join("; ")} }`;
  if (s.type === "list") return `list of ${s.min ?? 0}..${s.max ?? "n"}${o}: { ${Object.entries(s.of).map(([k, v]) => `${k}: ${fmt(v)}`).join("; ")} }`;
  return s.type + o;
};
console.log(`Blueprints for the ${lane} lane. An *anchor* is a word spoken in the same scene ("word", or "word#1" for its second use); the visual happens exactly when that word is said.\n`);
for (const { name, def } of defs) {
  console.log(`### ${name}${def.overlay ? " (overlay: lands on top of the previous part)" : ""}\n${about[name] || ""}\n`);
  for (const [k, s] of Object.entries(def.slots)) console.log(`- \`${k}\`: ${fmt(s)}`);
  console.log("");
}
