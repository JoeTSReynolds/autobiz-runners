import { createRequire as __autobizCreateRequire } from 'node:module'; const require = __autobizCreateRequire(import.meta.url);

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
export {
  postKey,
  submitAll,
  submitClip
};
