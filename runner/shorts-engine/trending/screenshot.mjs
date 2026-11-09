// Screenshots for news visuals (port of the Python Playwright kit).
//   node screenshot.mjs article <url> <out.png> [highlight]   mobile article shot, prints {path, found_highlight, title} as JSON
//   node screenshot.mjs card <json> <out.png>                 headline card from {outlet, date, headline, quote?}, transparent PNG
import { chromium } from 'playwright'

const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
const CONSENT = [/accept|agree/i, /got it|^\s*ok\b|continue/i]
const NUKE_FIXED = () => {
  for (const e of document.querySelectorAll('body *')) { const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') e.remove() }
  for (const e of [document.documentElement, document.body]) for (const [k, v] of [['overflow', 'visible'], ['height', 'auto'], ['position', 'static']]) e.style.setProperty(k, v, 'important')
}
// wraps the text of window.find()'s selection in <mark>, piece by piece so it works across elements
const MARK = (phrase) => {
  if (!window.find(phrase, false, false, true, false, false, false)) return false
  const r = getSelection().getRangeAt(0), root = r.commonAncestorContainer, first = []
  const w = document.createTreeWalker(root.nodeType === 3 ? root.parentNode : root, NodeFilter.SHOW_TEXT)
  const nodes = []; while (w.nextNode()) if (r.intersectsNode(w.currentNode)) nodes.push(w.currentNode)
  for (const n of nodes) {
    const s = n === r.startContainer ? r.startOffset : 0, e = n === r.endContainer ? r.endOffset : n.length
    if (e <= s) continue
    const m = n.splitText(s); m.splitText(e - s)
    const k = document.createElement('mark'); k.style.cssText = 'background:#FFE14D;color:#000;box-shadow:0 0 0 4px #FFE14D'
    m.replaceWith(k); k.appendChild(m); first.push(k)
  }
  getSelection().removeAllRanges()
  if (!first.length) return false
  first[0].id = '__hl'; return true
}

async function consent(page) {
  for (let i = 0; i < 2; i++) for (const rx of CONSENT) for (const fr of page.frames()) {
    try {
      const b = fr.getByRole('button', { name: rx }).first()
      await b.waitFor({ state: 'visible', timeout: 300 }); await b.click({ timeout: 1500 }); await page.waitForTimeout(500); break
    } catch { /* no consent button in this frame */ }
  }
  await page.evaluate(NUKE_FIXED)
}

// Output is width*scale px wide and ~9:16 (height capped at maxHeight CSS px).
async function article(url, outPng, highlight, width = 430, scale = 2.5, maxHeight = 1800) {
  const h = Math.min(maxHeight, Math.round(width * 16 / 9))
  const browser = await chromium.launch({ args: ['--no-sandbox'] })
  try {
    const ctx = await browser.newContext({ viewport: { width, height: h }, deviceScaleFactor: scale, isMobile: true, hasTouch: true, userAgent: UA, locale: 'en-GB' })
    const page = await ctx.newPage()
    await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500)
    await consent(page); await page.waitForTimeout(500); await page.evaluate(NUKE_FIXED)
    // no scrolling (some sites lock it): clip a full-page screenshot at the wanted document offset
    let top = await page.evaluate(() => { const e = document.querySelector('h1'); return e ? e.getBoundingClientRect().top + scrollY - 24 : 0 })
    let found = false
    if (highlight) {
      found = Boolean(await page.evaluate(MARK, highlight))
      if (found) top = (await page.evaluate(() => document.getElementById('__hl').getBoundingClientRect().top + scrollY)) - 0.35 * h
    }
    await page.waitForTimeout(600)
    const total = await page.evaluate(() => document.documentElement.scrollHeight)
    await page.screenshot({ path: outPng, fullPage: true, clip: { x: 0, y: Math.max(0, Math.min(top, total - h)), width, height: h } })
    return { path: outPng, found_highlight: found, title: await page.title() }
  } finally { await browser.close() }
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
// Fallback visual: white rounded headline card on a transparent PNG (~1000 px wide).
async function card({ outlet, date, headline, quote }, outPng) {
  const q = quote ? `<div style="margin-top:40px;padding-left:28px;border-left:8px solid #c00;font-style:italic;font-size:40px;line-height:1.3;color:#333">“${esc(quote)}”</div>` : ''
  const html = `<html><body style="margin:0;background:transparent"><div id="w" style="padding:50px;width:900px;box-sizing:content-box">
<div style="background:#fff;border-radius:36px;box-shadow:0 18px 50px rgba(0,0,0,.35);padding:64px 60px;font-family:'PT Serif','DejaVu Serif',Georgia,serif;color:#111">
<div style="font:700 28px 'DejaVu Sans',sans-serif;font-variant:small-caps;letter-spacing:.12em;color:#c00">${esc(outlet)}</div>
<div style="font:400 26px 'DejaVu Sans',sans-serif;color:#777;margin-top:10px">${esc(date)}</div>
<div style="font-weight:700;font-size:62px;line-height:1.15;margin-top:36px">${esc(headline)}</div>${q}</div></div></body></html>`
  const browser = await chromium.launch({ args: ['--no-sandbox'] })
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 1000 } })
    await page.setContent(html)
    await page.locator('#w').screenshot({ path: outPng, omitBackground: true })
    return { path: outPng }
  } finally { await browser.close() }
}

const [cmd, a, b, c] = process.argv.slice(2)
try {
  const res = cmd === 'article' ? await article(a, b, c) : cmd === 'card' ? await card(JSON.parse(a), b) : null
  if (!res) throw new Error('usage: screenshot.mjs article <url> <out.png> [highlight] | card <json> <out.png>')
  console.log(JSON.stringify(res))
} catch (e) { console.error(String(e?.message ?? e)); process.exit(1) }
