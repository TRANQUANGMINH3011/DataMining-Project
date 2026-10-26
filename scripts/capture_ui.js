const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const assetsDir = path.resolve(__dirname, '..', 'assets');

if (!fs.existsSync(assetsDir)) {
    fs.mkdirSync(assetsDir, { recursive: true });
}

async function capture() {
    console.log('Khởi chạy Edge headless để chụp ảnh giao diện Streamlit...');
    const browser = await puppeteer.launch({
        executablePath: edgePath,
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--window-size=1600,1000'
        ]
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000, deviceScaleFactor: 1.5 });

    console.log('Đang kết nối tới http://localhost:8501...');
    await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 30000 });

    // Đợi Streamlit render
    await new Promise(r => setTimeout(r, 3500));

    // Ẩn các popup / toast và thanh toolbar thừa
    await page.addStyleTag({
        content: `
            div[data-testid="stToolbar"] { display: none !important; }
            div[role="dialog"] { display: none !important; }
            .stAppDeployButton { display: none !important; }
            section[data-testid="stSidebar"] div[class*="stToast"] { display: none !important; }
        `
    });

    // Dismiss Streamlit skill popup nếu có
    try {
        await page.evaluate(() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const dismiss = btns.find(b => b.innerText && b.innerText.includes("Don't show again"));
            if (dismiss) dismiss.click();
        });
    } catch(e) {}

    await new Promise(r => setTimeout(r, 1000));

    // 1. Chụp Tab 1 (Executive BI)
    const tab1Path = path.join(assetsDir, 'ui_tab1_bi_overview.png');
    await page.screenshot({ path: tab1Path });
    console.log('-> Đã chụp Tab 1 (Executive BI):', tab1Path);

    // Lấy danh sách các tabs (div[role="tab"])
    const tabs = await page.$$('div[role="tab"]');
    console.log(`Tìm thấy ${tabs.length} tabs.`);

    // 2. Chụp Tab 2 (OLAP Studio)
    if (tabs.length >= 2) {
        await tabs[1].click();
        await new Promise(r => setTimeout(r, 2500));
        const tab2Path = path.join(assetsDir, 'ui_tab2_olap_ops.png');
        await page.screenshot({ path: tab2Path });
        console.log('-> Đã chụp Tab 2 (OLAP):', tab2Path);
    }

    // 3. Chụp Tab 3 (RFM Phân Khúc)
    if (tabs.length >= 3) {
        await tabs[2].click();
        await new Promise(r => setTimeout(r, 2500));
        const tab3Path = path.join(assetsDir, 'ui_tab3_rfm_segments.png');
        await page.screenshot({ path: tab3Path });
        console.log('-> Đã chụp Tab 3 (RFM):', tab3Path);
    }

    // 4. Chụp Tab 4 (Khai phá giỏ hàng & Gợi ý sản phẩm mua kèm)
    if (tabs.length >= 4) {
        await tabs[3].click();
        await new Promise(r => setTimeout(r, 2500));
        const tab4Path = path.join(assetsDir, 'ui_tab4_cross_sell.png');
        await page.screenshot({ path: tab4Path });
        console.log('-> Đã chụp Tab 4 (Cross-Sell Bundle):', tab4Path);
    }

    await browser.close();
    console.log(' HOÀN TẤT CHỤP TẤT CẢ 4 TAB GIAO DIỆN STREAMLIT THỰC TẾ!');
}

capture().catch(err => {
    console.error('Lỗi khi chụp giao diện:', err);
    process.exit(1);
});
