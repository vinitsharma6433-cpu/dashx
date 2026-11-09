// Thumbnail renderer: a real browser (Chromium via puppeteer, already installed for revideo) shapes the Hindi
// title correctly. Input (stdin JSON): {frame, logo, title, out}. Output: a 1080x1920 JPEG.
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const ROOT = path.join(__dirname, '..');
const b64 = f => fs.readFileSync(f).toString('base64');

async function main() {
  const {frame, logo, title, out} = JSON.parse(fs.readFileSync(0, 'utf8'));
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
  @font-face{font-family:'Noto Sans Devanagari';font-weight:100 900;src:url(data:font/ttf;base64,${b64(path.join(ROOT, 'fonts', 'NotoSansDevanagari.ttf'))}) format('truetype');}
  html,body{margin:0;width:1080px;height:1920px;overflow:hidden;background:#0b1220}
  .bg{position:absolute;inset:0;background:url(data:image/jpeg;base64,${b64(frame)}) center/cover}
  .top{position:absolute;left:0;right:0;top:0;height:640px;background:linear-gradient(to bottom,rgba(8,12,24,.88),rgba(8,12,24,.55) 62%,rgba(8,12,24,0))}
  .title{position:absolute;left:60px;right:60px;top:190px;text-align:center;font:900 168px/1.18 'Noto Sans Devanagari',sans-serif;color:#fde047;
    -webkit-text-stroke:10px #111827;paint-order:stroke fill;text-shadow:0 8px 0 rgba(0,0,0,.55)}
  .logo{position:absolute;left:50%;transform:translateX(-50%);top:1120px;width:560px;filter:drop-shadow(0 6px 10px rgba(0,0,0,.6))}
  </style></head><body><div class="bg"></div><div class="top"></div>
  <div class="title">${title.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</div>
  <img class="logo" src="data:image/png;base64,${b64(logo)}"></body></html>`;
  const browser = await puppeteer.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage();
    await page.setViewport({width: 1080, height: 1920});
    await page.setContent(html, {waitUntil: 'load'});
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({path: out, type: 'jpeg', quality: 92});
  } finally {
    await browser.close();
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
