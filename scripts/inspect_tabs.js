const puppeteer = require('puppeteer-core');
const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

(async () => {
    const browser = await puppeteer.launch({
        executablePath: edgePath,
        headless: 'new',
        args: ['--no-sandbox', '--disable-gpu']
    });
    const page = await browser.newPage();
    await page.goto('http://localhost:8501', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 3500));
    const allButtons = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('button, div, [role]')).map(el => ({
            tag: el.tagName,
            role: el.getAttribute('role'),
            text: el.innerText ? el.innerText.trim().slice(0, 30) : '',
            id: el.id,
            className: el.className
        })).filter(x => x.text && (x.text.includes('OLAP') || x.text.includes('Executive') || x.text.includes('RFM')));
    });
    console.log(JSON.stringify(allButtons.slice(0, 10), null, 2));
    await browser.close();
})();
