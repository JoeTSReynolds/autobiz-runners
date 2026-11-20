import { createRequire as __autobizCreateRequire } from 'node:module'; const require = __autobizCreateRequire(import.meta.url);

// scripts/content-rewards-scout-run.ts
import { execFile } from "node:child_process";
import { mkdir as mkdir2, readdir, readFile as readFile2, writeFile as writeFile2 } from "node:fs/promises";
import { dirname, join as join2 } from "node:path";
import { pathToFileURL as pathToFileURL2 } from "node:url";
import { promisify } from "node:util";
import { chromium as chromium2 } from "playwright";

// scripts/content-rewards-submit.ts
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
var CAMPAIGN = /^https:\/\/contentrewards\.com\/c\/campaigns\/[0-9a-f-]{36}$/i;
var ERROR = /can['’]t|invalid|already|\bnot\b|error|failed/i;
var ITEM_MS = 9e4;
async function submitClip(page, campaignUrl, clipUrl, shot) {
  try {
    await page.goto(campaignUrl, { waitUntil: "domcontentloaded", timeout: 3e4 });
    const open = page.getByRole("button", { name: "Submit clip", exact: true });
    const signIn = page.getByRole("link", { name: "Sign in" });
    const limit = page.getByText("Clip limit reached");
    await open.or(signIn).or(limit).first().waitFor({ timeout: 3e4 });
    if (page.url().includes("/login") || await signIn.count()) return { submitted: false, reason: "logged out" };
    if (await limit.count() && !(await open.count() && await open.isEnabled())) return { submitted: false, reason: "campaign clip limit reached (too many clips waiting for review)" };
    await open.click();
    const dialog = page.getByRole("dialog").filter({ hasText: /Before you submit|linked accounts|read the requirements/ }).first();
    const hold = dialog.getByRole("button", { name: "Hold to confirm" });
    const link = dialog.locator("input[type=url]");
    await hold.or(link).first().waitFor({ timeout: 15e3 });
    if (await hold.isVisible()) {
      const box2 = await hold.boundingBox();
      await page.mouse.move(box2.x + box2.width / 2, box2.y + box2.height / 2);
      await page.mouse.down();
      await page.waitForTimeout(1600);
      await page.mouse.up();
    }
    await link.fill(clipUrl, { timeout: 1e4 });
    const box = dialog.locator("input[type=checkbox]");
    if (!await box.isChecked()) await box.evaluate((input) => input.click());
    if (!await box.isChecked()) return { submitted: false, reason: "could not tick the requirements checkbox" };
    const send = dialog.getByRole("button", { name: "Submit clip", exact: true });
    for (const end = Date.now() + 2e4; await send.isDisabled(); await page.waitForTimeout(500)) {
      if (Date.now() > end) return { submitted: false, reason: "Content Rewards would not accept the link (submit stayed disabled)" };
    }
    const before = new Set((await dialog.innerText()).split("\n").map((line) => line.trim()));
    await send.click();
    const key = postKey(clipUrl);
    const listed = async () => {
      const r = await page.request.get(new URL("/api/submission/submissions?limit=50&creatorView=true&retainer=false", campaignUrl).href).catch(() => void 0);
      const json = r?.ok() ? await r.json().catch(() => void 0) : void 0;
      return Array.isArray(json?.data) ? !!key && JSON.stringify(json.data).includes(key) : void 0;
    };
    for (const end = Date.now() + 45e3; Date.now() < end; await page.waitForTimeout(1e3)) {
      const found = await listed();
      if (found) return { submitted: true };
      if (!await dialog.isVisible()) {
        if (found === void 0) return { submitted: true };
        continue;
      }
      const added = (await dialog.innerText()).split("\n").map((line) => line.trim()).filter((line) => line && !before.has(line)).join(" ");
      if (ERROR.test(added)) return { submitted: false, reason: added.replace(/\s+/g, " ").slice(0, 300) };
      if (/submitted|success/i.test(added)) return { submitted: true };
    }
    return { submitted: false, reason: "not in the submissions list 45 s after Submit" };
  } catch (error) {
    return { submitted: false, reason: (error instanceof Error ? error.message : String(error)).split("\n")[0].slice(0, 300) };
  } finally {
    if (shot) await page.screenshot({ path: shot }).catch(() => void 0);
  }
}
function postKey(url) {
  return /(?:shorts\/|[?&]v=|youtu\.be\/)([\w-]{11})/.exec(url)?.[1] ?? /instagram\.com\/(?:reel|p)\/([\w-]+)/.exec(url)?.[1] ?? "";
}
async function submitAll(env) {
  const { CR_SESSION_FILE, CR_CAMPAIGN_URL = "", PUBLISHED, CR_RESULT_FILE, CR_SHOTS_DIR } = env;
  const items = JSON.parse(await readFile(PUBLISHED, "utf8"));
  const results = [];
  const campaignOf = ({ campaign }) => typeof campaign === "string" && CAMPAIGN.test(campaign) ? campaign : CAMPAIGN.test(CR_CAMPAIGN_URL) ? CR_CAMPAIGN_URL : void 0;
  const browser = items.some((item) => campaignOf(item) && item.url.startsWith("https://")) ? await chromium.launch({ executablePath: process.env.CR_CHROME || void 0 }).catch(() => void 0) : void 0;
  try {
    const context = browser && await browser.newContext({ storageState: CR_SESSION_FILE });
    if (CR_SHOTS_DIR) await mkdir(CR_SHOTS_DIR, { recursive: true });
    for (const [index, item] of items.entries()) {
      const { platform, url } = item;
      const campaign = campaignOf(item);
      let result;
      if (!url.startsWith("https://")) result = { submitted: false, reason: "not an https URL" };
      else if (!campaign) result = { submitted: false, reason: "no campaign URL" };
      else if (!context) result = { submitted: false, reason: "browser did not start" };
      else {
        const page = await context.newPage();
        let timer;
        result = await Promise.race([
          submitClip(page, campaign, url, CR_SHOTS_DIR && join(CR_SHOTS_DIR, `${index}.png`)),
          new Promise((resolve) => {
            timer = setTimeout(() => resolve({ submitted: false, reason: "timed out" }), ITEM_MS);
          })
        ]);
        clearTimeout(timer);
        await page.close().catch(() => void 0);
      }
      results.push({ platform, url, ...result });
    }
  } finally {
    await browser?.close().catch(() => void 0);
    await writeFile(CR_RESULT_FILE, JSON.stringify(results));
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await submitAll(process.env).catch((error) => console.error(`Content Rewards submit failed: ${error instanceof Error ? error.message : error}`));
}

// scripts/content-rewards-scout.ts
var GAMING = ["gaming", "streamer", "twitch", "kick", "gta", "fortnite", "roblox", "minecraft", "mobile gaming", "pc gaming"];
var PODCAST = ["personal brand", "business", "entrepreneurship", "coach & mentor", "coaching & consulting", "content creator"];
var BLOCK = ["gambling", "casino", "betting", "bet", "parlay", "poker", "prop firm", "prop trading", "funded trader", "trading", "day trading", "forex", "crypto", "memecoin", "token", "nft", "adult", "onlyfans", "politics", "political", "election", "ugc", "sound campaign"];
var BLOCK_RE = new RegExp(`(?<![a-z])(${BLOCK.join("|")})s?(?![a-z])`, "i");
var payload = (html) => [...html.matchAll(/self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)/g)].map((m) => JSON.parse(m[1])).join("");
function parseDiscoverApi(json) {
  const data = json?.data;
  if (!Array.isArray(data)) return [];
  return data.filter((o) => o && typeof o.id === "string" && o.status === "active").map((o) => ({
    id: o.id,
    title: String(o.name ?? ""),
    brand: String(o.organizationName ?? ""),
    categories: (o.categories ?? []).map((c) => String(c.name)),
    type: o.payoutType,
    platforms: o.platforms ?? [],
    requiresApplication: !!o.requiresApplication,
    availableBudget: (o.budgetCents - (o.metrics?.budgetSpentCents ?? 0)) / 100,
    budgetTotal: o.budgetCents / 100,
    creators: o.metrics?.creatorCount ?? 0,
    rate: (o.cpmMaxRateCents ?? 0) / 100,
    url: `https://contentrewards.com/c/campaigns/${o.id}`,
    description: o.description,
    terms: (o.payouts ?? []).filter((p) => p.payoutType === "cpm").map((p) => ({ platform: String(p.platform), rate: p.rateCents / 100, minPayout: p.minPayoutCents / 100, maxPayout: p.maxPayoutCents / 100 })),
    references: (o.referenceMaterials ?? []).map((r) => r.url)
  }));
}
function routeChannel(c) {
  const names = c.categories.map((n) => n.toLowerCase());
  return names.some((n) => GAMING.includes(n)) ? "gaming" : names.some((n) => n.includes("podcast") || PODCAST.includes(n)) ? "podcast" : null;
}
var blocked = (c) => {
  const m = BLOCK_RE.exec(`${c.categories.join(" | ")} | ${c.title} | ${c.brand}`);
  return m ? `blocked: ${m[1].toLowerCase()}` : null;
};
function rank(list, { minBudget = 1e3 } = {}) {
  const score = (c) => c.rate * c.availableBudget / Math.max(c.creators, 1);
  return list.filter((c) => c.type === "cpm" && !c.requiresApplication && c.platforms.includes("youtube") && c.platforms.includes("instagram") && c.availableBudget >= minBudget && routeChannel(c) && !blocked(c)).sort((a, b) => score(b) - score(a));
}
function viewsToMinimum(terms, platform) {
  const t = terms.find((x) => x.platform === platform);
  return t && t.rate > 0 ? Math.ceil(t.minPayout / t.rate * 1e3) : Infinity;
}
var passesMinimum = ({ terms }, { maxViewsToMinimum = 2e3 } = {}) => viewsToMinimum(terms, "youtube") <= maxViewsToMinimum;
async function draftRecord(page, candidate, channel) {
  const { text, cards, links } = await page.evaluate(() => {
    const all = [...document.querySelectorAll("[data-card-shell]")];
    const card = (name) => all.find((c) => c.querySelector("span:not(:empty)")?.textContent?.trim() === name);
    const paras = (name) => [...card(name)?.querySelectorAll("p") ?? []].map((p) => ({ label: p.textContent.trim(), next: p.nextElementSibling?.textContent ?? "" }));
    return {
      text: { brief: paras("Brief").map((p) => p.label).join("\n"), requirements: paras("Creator requirements").map((p) => p.label).join("\n") },
      cards: Object.fromEntries(["Instagram", "TikTok", "YouTube"].map((n) => [n.toLowerCase(), paras(n)])),
      links: [...card("Reference materials")?.querySelectorAll("a[href]") ?? []].map((a) => ({ url: a.getAttribute("href"), title: a.textContent.trim() }))
    };
  });
  const money = (t) => Number(t.replace(/[^0-9.]/g, ""));
  const rates = {};
  for (const [name, p] of Object.entries(cards)) {
    const next = (label) => money(p.find((x) => x.label === label)?.next ?? "");
    if (p.length) rates[name] = { rate: next("Per 1K views"), minPayout: next("Min payout"), maxPayout: next("Max payout") };
  }
  const sources = [];
  for (const { url, title } of links) {
    const id = /(?:youtube\.com|youtu\.be)\//.test(url) ? postKey(url) : "";
    if (id && !sources.some((x) => x.id === id)) sources.push({ id, url, title, channel: "", duration: 0 });
  }
  return {
    id: candidate.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || candidate.id.slice(0, 8),
    url: candidate.url,
    channel,
    active: false,
    brief: text.brief,
    requirements: text.requirements,
    checklist: "",
    featured: "",
    disclosure: "",
    rates,
    sources,
    driveLinks: links.filter((l) => /^https:\/\/drive\.google\.com\//.test(l.url)).map((l) => l.url),
    needsSourceInfo: true
  };
}
async function audit(records, fetchPublic, { retireBelow = 100 } = {}) {
  const out = [];
  for (const { id, url } of records) {
    try {
      const html = await fetchPublic(url), s = payload(html);
      const cents = (key) => Number(new RegExp(`"${key}":(\\d+)`).exec(s)?.[1] ?? NaN);
      const available = (cents("budgetCents") - cents("budgetSpentCents")) / 100, status = /"status":"(\w+)","statusChangedAt"/.exec(s)?.[1];
      if (!Number.isFinite(available) || !status) {
        out.push({ id, url, availableBudget: null, accepting: true, retire: false, reason: "unreadable page" });
        continue;
      }
      const accepting = status === "active" && !/not accepting|campaign (?:has )?ended/i.test(html.replace(/<[^>]*>/g, " "));
      const reason = !accepting ? `not accepting (${status})` : available < retireBelow ? `budget $${available} below $${retireBelow}` : "";
      out.push({ id, url, availableBudget: available, accepting, retire: !!reason, reason });
    } catch (error) {
      out.push({ id, url, availableBudget: null, accepting: true, retire: false, reason: `fetch failed: ${error instanceof Error ? error.message : error}` });
    }
  }
  return out;
}
var submitButton = (page) => page.getByRole("button", { name: "Submit clip", exact: true });
async function joinCampaign(page, url, waitMs = 2e4) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 3e4 });
    const submit = submitButton(page), join3 = page.getByRole("button", { name: "Join Campaign" }).first(), signIn = page.getByRole("link", { name: "Sign in" });
    await submit.or(join3).or(signIn).first().waitFor({ timeout: 3e4 });
    if (page.url().includes("/login") || await signIn.count()) return { joined: false, reason: "logged out" };
    if (await submit.count()) return { joined: true, already: true };
    await join3.click();
    let confirmed = false;
    for (const end = Date.now() + waitMs; Date.now() < end; await page.waitForTimeout(250)) {
      if (await submit.count()) return { joined: true };
      const dialog = page.getByRole("dialog").filter({ hasNotText: /cookie/i }).first();
      const ok = dialog.getByRole("button", { name: /^(join|confirm|accept|continue)/i }).first();
      if (confirmed || !await ok.isVisible()) continue;
      for (const box of await dialog.locator("input[type=checkbox]").all()) if (!await box.isChecked()) await box.evaluate((input) => input.click());
      if (await ok.isEnabled()) {
        await ok.click();
        confirmed = true;
      }
    }
    return { joined: false, reason: `no Submit clip button ${waitMs / 1e3} s after Join` };
  } catch (error) {
    return { joined: false, reason: (error instanceof Error ? error.message : String(error)).split("\n")[0].slice(0, 300) };
  }
}
async function readSubmitChecklist(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 3e4 });
  await submitButton(page).click();
  const dialog = page.getByRole("dialog").filter({ hasText: /Before you submit|linked accounts|read the requirements/ }).first();
  const hold = dialog.getByRole("button", { name: "Hold to confirm" });
  await hold.or(dialog.locator("input[type=url]")).first().waitFor({ timeout: 15e3 });
  const text = await hold.isVisible() ? (await dialog.innerText()).replace("Hold to confirm", "").replace(/\n\s*\n+/g, "\n").trim() : "";
  await page.keyboard.press("Escape");
  if (await dialog.isVisible()) await dialog.getByRole("button", { name: /cancel|close/i }).first().click({ timeout: 3e3 }).catch(() => void 0);
  return text;
}
async function fitCheck(candidates, ask, n = 5) {
  const top = candidates.slice(0, n);
  const prompt = `Our pipeline makes YouTube Shorts and Instagram Reels from long-form video. For each campaign below, decide whether we can clip it well. Podcast lane: long-form talking-head video with clear speech. Reject gameplay, trailers, music videos, product demos without talking, and non-English content.

${top.map((c) => JSON.stringify({ id: c.id, title: c.title, categories: c.categories, description: c.description?.slice(0, 400) })).join("\n")}

Reply with only a JSON array: [{"id": "...", "fit": true|false, "reason": "..."}], one entry per campaign.`;
  let verdicts = [];
  try {
    const reply = await ask(prompt), from = reply.indexOf("["), to = reply.lastIndexOf("]");
    const parsed = JSON.parse(reply.slice(from, to + 1));
    if (Array.isArray(parsed)) verdicts = parsed;
  } catch {
  }
  return top.map((c) => {
    const v = verdicts.find((x) => typeof x === "object" && x !== null && x.id === c.id && typeof x.fit === "boolean");
    return v ? { id: c.id, fit: v.fit, reason: String(v.reason ?? "") } : { id: c.id, fit: false, reason: "no valid verdict" };
  });
}
function report({ retired, drafted, suggested, blocked: skipped, wouldJoin }) {
  const lines = [
    `Retired (${retired.length})`,
    ...retired.map((r) => `- ${r.id}: ${r.reason}`),
    `Joined and drafted (${drafted.length})`,
    ...drafted.map((d) => `- ${d.title} ${d.url}`),
    ...wouldJoin ? [`Would join (dry run) (${wouldJoin.length})`, ...wouldJoin.map((w) => `- ${w.title} ${w.url}`)] : [],
    `Gaming suggestions (${suggested.length}), not joined`,
    ...suggested.map((c) => `- ${c.title} ($${c.rate}/1K, $${Math.round(c.availableBudget)} left) ${c.url}`),
    `Skipped ${skipped} blocked`
  ].join("\n");
  return lines.length <= 3500 ? lines : `${lines.slice(0, 3490)}
...`;
}

// scripts/content-rewards-scout-run.ts
var DISCOVER = "https://contentrewards.com/api/campaign/campaigns/discover?collapseGroups=true&limit=50&view=summary";
var MAX_PAGES = 12;
var message = (error) => (error instanceof Error ? error.message : String(error)).split("\n")[0].slice(0, 300);
var uuidOf = (url) => /[0-9a-f-]{36}$/i.exec(url)?.[0]?.toLowerCase() ?? "";
var readJson = async (path) => JSON.parse(await readFile2(path, "utf8"));
var write = async (path, text) => {
  await mkdir2(dirname(path), { recursive: true });
  await writeFile2(path, text);
};
async function knownRecords(dir) {
  const out = [];
  for (const slug of await readdir(dir).catch(() => [])) {
    try {
      const file = await readJson(join2(dir, slug, "business.json"));
      for (const { id, url } of file.business?.settings?.campaigns ?? []) if (id && url) out.push({ id, url });
    } catch {
    }
  }
  return out;
}
async function scout(env, deps) {
  const { BUSINESSES_DIR = "businesses", SCOUT_STATE = "data/scout/seen.json", SCOUT_OUT = "scout-out" } = env;
  const join_ = env.SCOUT_JOIN === "1", maxJoins = Number(env.SCOUT_MAX_JOINS ?? 2), recheckMs = Number(env.SCOUT_RECHECK_DAYS ?? 14) * 864e5;
  const site = deps.site ?? { joinCampaign, draftRecord, readSubmitChecklist };
  const notes = [];
  const page = await deps.openPage();
  try {
    const all = [];
    for (let cursor = "", n = 0; n < MAX_PAGES; n++) {
      const reply = await deps.fetchJson(cursor ? `${DISCOVER}&cursor=${encodeURIComponent(cursor)}` : DISCOVER);
      for (const c of parseDiscoverApi(reply)) if (!all.some((x) => x.id === c.id)) all.push(c);
      cursor = String(reply?.pagination?.nextCursor ?? "");
      if (!cursor) break;
    }
    if (!all.length) throw new Error("Discover API returned no campaigns. Check that contentrewards.com is up; if joins also fail, the session may have expired: run `npm run cr:connect` and update the CR_SESSION secret.");
    const records = await knownRecords(BUSINESSES_DIR);
    const retired = (await audit(records, deps.fetchPublic)).filter((a) => a.retire).map((a) => ({ id: a.id, reason: a.reason }));
    const seen = await readJson(SCOUT_STATE).catch(() => ({}));
    const known = new Set(records.map((r) => uuidOf(r.url)));
    const fresh = rank(all).filter((c) => !known.has(c.id) && !(seen[c.id] && seen[c.id].verdict !== "failed" && deps.now() - Date.parse(seen[c.id].at) < recheckMs));
    const suggested = fresh.filter((c) => routeChannel(c) === "gaming").slice(0, 5);
    const isPodcast = (c) => c.categories.some((n) => /podcast/i.test(n));
    const eligible = fresh.filter((c) => routeChannel(c) === "podcast" && passesMinimum(c)).sort((a, b) => Number(isPodcast(b)) - Number(isPodcast(a)));
    const mark = (id, verdict) => {
      seen[id] = { verdict, at: new Date(deps.now()).toISOString() };
    };
    const drafted = [], wouldJoin = [];
    const top = eligible.slice(0, 10), fits = top.length ? await fitCheck(top, deps.ask, 10) : [];
    const judged = fits.filter((f) => f.reason !== "no valid verdict");
    if (top.length && judged.length < fits.length) notes.push(`Fit check gave no usable answer for ${fits.length - judged.length} of ${fits.length} campaigns; they will be asked again next run`);
    for (const f of judged.filter((f2) => !f2.fit)) {
      mark(f.id, "unfit");
      notes.push(`${top.find((x) => x.id === f.id).title}: not a fit (${f.reason})`);
    }
    for (const { id } of fits.filter((f) => f.fit).slice(0, maxJoins)) {
      const c = top.find((x) => x.id === id);
      if (!join_) {
        wouldJoin.push({ title: c.title, url: c.url });
        continue;
      }
      try {
        const joined = await site.joinCampaign(page, c.url);
        if (!joined.joined) {
          mark(id, "failed");
          notes.push(`${c.title}: join failed (${joined.reason})`);
          continue;
        }
        mark(id, "joined");
        const record = await site.draftRecord(page, c, "podcast");
        record.checklist = await site.readSubmitChecklist(page, c.url).catch((error) => {
          notes.push(`${c.title}: checklist not read (${message(error)})`);
          return "";
        });
        await write(join2(SCOUT_OUT, "proposed", `${record.id}.json`), `${JSON.stringify(record, null, 2)}
`);
        drafted.push({ id: record.id, title: c.title, url: c.url });
      } catch (error) {
        mark(id, "failed");
        notes.push(`${c.title}: ${message(error)}`);
      }
    }
    await write(SCOUT_STATE, `${JSON.stringify(seen, null, 2)}
`);
    const text = [report({ retired, drafted, suggested, blocked: all.filter(blocked).length, wouldJoin: join_ ? void 0 : wouldJoin }), ...notes.length ? ["Notes", ...notes.map((n) => `- ${n}`)] : []].join("\n");
    await write(join2(SCOUT_OUT, "report.txt"), text);
    console.log(text);
    return text;
  } catch (error) {
    await write(join2(SCOUT_OUT, "report.txt"), `Campaign scout failed: ${message(error)}`).catch(() => void 0);
    throw error;
  } finally {
    await page.close().catch(() => void 0);
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL2(process.argv[1]).href) {
  const run = promisify(execFile);
  const real = {
    async openPage() {
      const browser = await chromium2.launch({ executablePath: process.env.CR_CHROME || void 0 });
      const page = await (await browser.newContext({ storageState: process.env.CR_SESSION_FILE })).newPage();
      const close = page.close.bind(page);
      page.close = async (...args) => {
        await close(...args).catch(() => void 0);
        await browser.close();
      };
      return page;
    },
    fetchJson: async (url) => (await fetch(url, { signal: AbortSignal.timeout(2e4) })).json(),
    fetchPublic: async (url) => (await fetch(url, { signal: AbortSignal.timeout(2e4) })).text(),
    ask: async (prompt) => (await run("claude", ["-p", prompt, "--model", process.env.SCOUT_MODEL || "claude-haiku-5-5"], { timeout: 18e4, maxBuffer: 1e7 })).stdout,
    now: Date.now
  };
  await scout(process.env, real).catch((error) => {
    console.error(`Campaign scout failed: ${message(error)}`);
    process.exitCode = 1;
  });
}
export {
  scout
};
