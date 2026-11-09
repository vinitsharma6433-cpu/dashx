// Measure how a subtitle wraps in a real browser, with the same font and size as the reel
// (Noto Sans Devanagari 700, 56 px), so a single word alone on a line can be found and avoided.
//
//   node scripts/subtitle_lines.js < input.json
//   input : {"fontSize": 56, "items": [{"text": "...", "width": 900}, {"text": "..."}]}
//   output: {"items": [{"text", "width", "lines": [{"text", "words"}], "ok", "fitted"}]}
//
// An item with a "width" is only measured. An item without one is FITTED: the widest width (900 down to
// 480 px) is chosen where every line has at least 2 words (or the text fits on one line), and the answer
// also holds for width +-10 px, so small differences between this measurement and the renderer do not
// matter. "ok" is false when no width works (the line must be rephrased).

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const FONT_FILE = path.join(__dirname, '..', 'fonts', 'NotoSansDevanagari.ttf');

function pageFunctions() {
  window.layout = (text, width, fontSize) => {
    const div = document.createElement('div');
    div.style.cssText =
      `position:absolute;left:0;top:0;width:${width}px;font:700 ${fontSize}px 'Noto Sans Devanagari';` +
      `line-height:${Math.round(fontSize * 1.55)}px;text-align:center;white-space:normal;`;
    const words = text.split(/\s+/).filter(Boolean);
    words.forEach((w, wi) => {
      // a hyphen is a possible break point, so each part gets its own span
      w.split(/(?<=-)/).forEach(part => {
        const sp = document.createElement('span');
        sp.textContent = part;
        sp.dataset.w = String(wi);
        div.appendChild(sp);
      });
      if (wi < words.length - 1) div.appendChild(document.createTextNode(' '));
    });
    document.body.appendChild(div);
    const lines = [];
    let lastTop = null;
    for (const sp of div.querySelectorAll('span')) {
      const top = Math.round(sp.getBoundingClientRect().top);
      if (lastTop === null || Math.abs(top - lastTop) > 5) {
        lines.push([]);
        lastTop = top;
      }
      lines[lines.length - 1].push({w: sp.dataset.w, t: sp.textContent});
    }
    div.remove();
    return lines.map(l => ({text: l.map(x => x.t).join(' '), words: new Set(l.map(x => x.w)).size}));
  };
}

const good = lines => lines.length === 1 || lines.every(l => l.words >= 2);

async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const fontSize = input.fontSize || 56;
  const font64 = fs.readFileSync(FONT_FILE).toString('base64');
  const browser = await puppeteer.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage();
    await page.setContent(
      `<style>@font-face{font-family:'Noto Sans Devanagari';font-weight:100 900;` +
        `src:url(data:font/ttf;base64,${font64}) format('truetype');}</style><body></body>`,
    );
    await page.evaluate(`(${pageFunctions.toString()})()`);
    await page.evaluate(size => document.fonts.load(`700 ${size}px 'Noto Sans Devanagari'`), fontSize);
    await page.evaluate(() => document.fonts.ready);

    const layout = (text, width) => page.evaluate((t, w, s) => window.layout(t, w, s), text, width, fontSize);
    const items = [];
    for (const it of input.items) {
      if (it.width) {
        const lines = await layout(it.text, it.width);
        items.push({text: it.text, width: it.width, lines, ok: good(lines), fitted: false});
        continue;
      }
      let found = null;
      for (let w = 900; w >= 480 && !found; w -= 10) {
        const [a, b, c] = [await layout(it.text, w - 10), await layout(it.text, w), await layout(it.text, w + 10)];
        if (good(a) && good(b) && good(c)) found = {width: w, lines: b};
      }
      items.push(
        found
          ? {text: it.text, width: found.width, lines: found.lines, ok: true, fitted: true}
          : {text: it.text, width: 900, lines: await layout(it.text, 900), ok: false, fitted: true},
      );
    }
    process.stdout.write(JSON.stringify({items}));
  } finally {
    await browser.close();
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
