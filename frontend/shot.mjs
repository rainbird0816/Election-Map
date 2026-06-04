import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForSelector("svg path", { timeout: 8000 });

// 채색된(회색 아닌) path 개수 집계
const stats = await page.evaluate(() => {
  const paths = [...document.querySelectorAll("svg path")];
  const fills = {};
  for (const p of paths) {
    const f = (p.getAttribute("fill") || "").toUpperCase();
    fills[f] = (fills[f] || 0) + 1;
  }
  return { total: paths.length, fills };
});
console.log("PATHS:", JSON.stringify(stats));

await page.screenshot({ path: "map_default.png", fullPage: true });

// 서울 클릭 -> 지역 상세
const seoul = await page.$("svg path"); // 첫 path
await seoul.click();
await page.waitForTimeout(1200);
await page.screenshot({ path: "map_seoul.png", fullPage: true });

console.log("CONSOLE_ERRORS:", JSON.stringify(errors));
await browser.close();
