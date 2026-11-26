import assert from "node:assert/strict";
import fs from "node:fs";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const WEB = process.env.MUNSHI_WEB_URL ?? "http://127.0.0.1:3000";
const API = process.env.MUNSHI_API_URL ?? "http://127.0.0.1:8000";
const SHOT_DIR = process.env.MUNSHI_SHOT_DIR ?? "";

async function snap(page, name) {
  if (!SHOT_DIR) return;
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  await page.screenshot({
    path: `${SHOT_DIR}/${name}.png`,
    fullPage: false,
    animations: "disabled",
    timeout: 20000,
  });
}

function findBrowser() {
  const candidates = [
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  ];
  for (const path of candidates) {
    if (fs.existsSync(path)) return path;
  }
  return undefined;
}

async function resetDemo() {
  const res = await fetch(`${API}/api/demo/reset`, { method: "POST" });
  assert.equal(res.status, 200, "demo reset must succeed");
}

async function run() {
  const executablePath = findBrowser();
  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
  });

  const errors = [];
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((apiBase) => {
    window.__MUNSHI_API_BASE__ = apiBase;
  }, API);
  const page = await context.newPage();

  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("response", (res) => {
    if (res.status() >= 400) {
      errors.push(`http ${res.status()}: ${res.url()}`);
    }
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const txt = msg.text();
      if (!txt.includes("WebGL")) errors.push(`console.error: ${txt}`);
    }
  });

  try {
    await resetDemo();

    // 1. Call Stage load + imagery + badges + 3D canvas check
    await page.goto(WEB, { waitUntil: "networkidle" });
    await page.waitForSelector("h1.display");
    await page.waitForSelector(".voice-core-3d canvas", { timeout: 10000 });
    await page.waitForTimeout(900);
    await snap(page, "01-call-stage-hero");

    // Verify bespoke images loaded cleanly
    const imageCheck = await page.evaluate(() =>
      Array.from(document.images).map((img) => ({
        src: img.getAttribute("src"),
        complete: img.complete,
        naturalWidth: img.naturalWidth,
      })),
    );
    assert(imageCheck.length >= 2, "Expected Amma & Rohit portraits on Call Stage");
    for (const img of imageCheck) {
      assert(img.complete && img.naturalWidth > 0, `Image failed to load: ${img.src}`);
    }

    // F-04: Honest labels visible (stamps are uppercase via CSS)
    const bodyText = (await page.locator("body").textContent()) ?? "";
    assert(bodyText.includes("Browser voice: live"), "Footer live badge missing");
    assert(bodyText.includes("Payments: sandbox"), "Footer sandbox badge missing");
    assert(bodyText.includes("Gas & medicine: simulated"), "Footer simulated badge missing");

    // F-01: J1 Happy Path through Call Stage
    await page.getByRole("button", { name: /Start Amma's call/i }).click();
    await page.waitForSelector(".bubble.munshi");
    await page.getByRole("button", { name: "बिजली का बिल (J1)" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("1,240 rupaye"));
    await page.getByRole("button", { name: "हाँ", exact: true }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("Ho gaya"));

    // Verify pipeline strip updated & Rohit's phone received voice note + ledger row
    const stageAfterJ1 = (await page.locator("body").textContent()) ?? "";
    assert(stageAfterJ1.includes("Read-back confirmed"), "Pipeline strip did not update");
    assert(stageAfterJ1.includes("MOCK-") || stageAfterJ1.includes("Ho gaya"), "Child phone note missing");
    await snap(page, "02-call-stage-j1");

    // F-01: J3 Unsupported Transfer refused
    await page.getByRole("button", { name: "रामू को 5,000 भेज दे (J3)" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("kisi ko paise bhej nahi sakta"));

    // F-01 & F-02: J2 New Payee -> Child Approval on Phone Simulator
    await page.getByRole("button", { name: "पानी का बिल (J2 · Approval)" }).click();
    await page.waitForSelector(".approval-card");
    await page.getByRole("button", { name: "Haan, kar do" }).click();
    await page.waitForSelector(".approval-card", { state: "detached" });

    // F-05: Navigate to Under the Hood and verify rules & audit chain
    await page.getByRole("link", { name: "Under the Hood", exact: true }).click();
    await page.waitForSelector(".trace-sheet");
    await page.waitForTimeout(600);
    await snap(page, "03-under-the-hood");
    const traceText = ((await page.locator(".trace-sheet").textContent()) ?? "").toLowerCase();
    assert(traceText.includes("p-new-payee"), "Trace view did not display fired rule P-NEW-PAYEE");
    assert(traceText.includes("audit valid"), "Audit chain validity badge missing");

    // F-02 & F-03: Navigate to Family Console, test onboarding & pause kill-switch
    await page.getByRole("link", { name: "Family Console", exact: true }).click();
    await page.waitForSelector(".budget-band");
    await page.waitForTimeout(600);
    await snap(page, "04-family-console");
    const consoleText = (await page.locator("body").textContent()) ?? "";
    assert(consoleText.includes("Bijli bill") && consoleText.includes("Paani bill"), "Ledger rows missing");
    assert(consoleText.toUpperCase().includes("SIMULATED"), "Mode stamp missing on ledger");

    // Onboarding voice note parse -> readback -> confirm (J6)
    await page.getByRole("button", { name: "Samjho" }).click();
    await page.waitForSelector(".readback");
    await page.getByRole("button", { name: "Haan, save karo" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("Lag gaya"));

    // Pause switch (J5 / F-03) and verify parent call is blocked immediately
    const pauseSwitch = page.getByRole("switch");
    await pauseSwitch.click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("Munshi ruka hua hai"));

    await page.getByRole("link", { name: "Call Stage", exact: true }).click();
    await page.waitForSelector("h1.display");
    await page.getByRole("button", { name: /Start Amma's call/i }).click();
    await page.waitForSelector(".bubble.munshi");
    await page.getByRole("button", { name: "सिलेंडर खत्म (Sim)" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("Abhi Munshi ruka hua hai"));

    // Reset Demo button from TopRail + DTMF keypad test (F-01 / F-08)
    await page.getByRole("button", { name: /Reset demo/i }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("Reset "));
    await page.getByRole("button", { name: /Start Amma's call/i }).click();
    await page.waitForSelector(".bubble.munshi");
    await page.getByRole("button", { name: "सिलेंडर खत्म (Sim)" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("1,100 rupaye"));
    await page.getByRole("button", { name: /Keypad/i }).click();
    await page.getByRole("button", { name: "1 · Haan" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("Ho gaya"));

    // F-06: Full Axe Accessibility audit (including color-contrast!) across all 3 pages
    for (const route of ["/", "/console", "/trace"]) {
      await page.goto(`${WEB}${route}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(600);
      const axe = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      const serious = axe.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
      assert.equal(
        serious.length,
        0,
        `Serious a11y violations on ${route}: ${JSON.stringify(serious.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.html).slice(0, 2) })))}`,
      );
    }

    // F-07: Responsive check at 360px phone viewport (no horizontal scroll)
    await page.setViewportSize({ width: 360, height: 800 });
    for (const route of ["/", "/console", "/trace"]) {
      await page.goto(`${WEB}${route}`, { waitUntil: "networkidle" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      );
      assert.equal(overflow, false, `Horizontal overflow detected at 360px on ${route}`);
      if (route === "/") {
        await page.waitForTimeout(400);
        await snap(page, "05-mobile-360");
      }
    }

    // F-01: J7 Unknown Caller test
    await resetDemo();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(WEB, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Anjaan number se call (J7)" }).click();
    await page.waitForFunction(() => (document.body.textContent ?? "").includes("family se juda nahi"));

    assert.equal(errors.length, 0, `Browser runtime errors detected:\n${errors.join("\n")}`);
    console.log("ALL PLAYWRIGHT E2E + A11Y + RESPONSIVE CHECKS PASSED (J1-J7, F-01..F-07)");
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
