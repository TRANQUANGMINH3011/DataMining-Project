const puppeteer = require('puppeteer-core');
const path = require('path');

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const assetsDir = path.resolve(__dirname, '..', 'assets');

(async () => {
    const browser = await puppeteer.launch({
        executablePath: edgePath,
        headless: 'new',
        args: ['--no-sandbox', '--disable-gpu', '--window-size=1600,1000']
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000, deviceScaleFactor: 1.5 });
    await page.goto('http://localhost:8501', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 3000));

    await page.addStyleTag({
        content: `
            div[data-testid="stToolbar"] { display: none !important; }
            div[role="dialog"] { display: none !important; }
            .stAppDeployButton { display: none !important; }
        `
    });

    const tabs = await page.$$('div[role="tab"]');
    if (tabs.length >= 4) {
        await tabs[3].click();
        await new Promise(r => setTimeout(r, 2000));
        await page.evaluate(() => {
            const main = document.querySelector('section.main') || document.querySelector('[data-testid="stMain"]');
            if (main) {
                main.scrollTop = main.scrollHeight;
            } else {
                window.scrollTo(0, document.body.scrollHeight);
            }
        });
        await new Promise(r => setTimeout(r, 1500));
        const bundlePath = path.join(assetsDir, 'ui_tab4_bundle_cards.png');
        await page.screenshot({ path: bundlePath });
        console.log('-> Đã chụp Gói Sản phẩm Bundle Mua kèm:', bundlePath);
    }
    await browser.close();
})();
