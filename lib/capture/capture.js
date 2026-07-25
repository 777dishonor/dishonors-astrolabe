const puppeteer = require('puppeteer');

(async () => {
  const [htmlFile, outPng] = process.argv.slice(2);
  if (!htmlFile || !outPng) {
    console.error('用法: node capture.js <html> <output.png>');
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox'],
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 900, height: 900 });

    // 收集控制台消息
    page.on('console', msg => console.log('PAGE_LOG:', msg.type(), msg.text()));
    page.on('pageerror', err => console.log('PAGE_ERR:', err.message));

    const fileUrl = 'file:///' + require('path').resolve(htmlFile).replace(/\\/g, '/');
    console.log('Loading:', fileUrl);
    await page.goto(fileUrl, { waitUntil: 'load', timeout: 15000 });

    // 等 3 秒让 JS 跑完
    await new Promise(r => setTimeout(r, 3000));

    // 检查页面 body 内容
    const bodyHTML = await page.evaluate(() => document.body.innerHTML.substring(0, 500));
    console.log('BODY_PREVIEW:', bodyHTML);

    await page.screenshot({ path: outPng });
    console.log('[OK]', outPng);
  } finally {
    await browser.close();
  }
})();
