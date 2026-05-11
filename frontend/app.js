/**
 * FinXtract — Client v2.0
 * ================================
 * Orchestrates: Config → Upload → Gemini AI Extraction → Excel Download
 */

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8002'
    : 'https://financial-statement-scraping.onrender.com';

const MAX_DAILY_REQUESTS = 20;

// ── DOM Elements ──────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const el = {
    form: $('bctcForm'),
    tickerInput: $('tickerInput'),
    periodType: $('periodType'),
    yearFrom: $('yearFrom'),
    yearTo: $('yearTo'),
    formSection: $('formSection'),
    uploadSection: $('uploadSection'),
    progressSection: $('progressSection'),
    resultSection: $('resultSection'),
    uploadContainer: $('uploadContainer'),
    processAiBtn: $('processAiBtn'),
    backToConfigBtn: $('backToConfigBtn'),
    progressFill: $('progressFill'),
    progressText: $('progressText'),
    progressMessage: $('progressMessage'),
    downloadBtn: $('downloadBtn'),
    newQueryBtn: $('newQueryBtn'),
    serverStatus: $('serverStatus'),
    statusDot: $('statusDot'),
    apiUsageBadge: $('apiUsageBadge'),
    apiUsageText: $('apiUsageText'),
    stepsNav: $('stepsNav'),
    resultSummary: $('resultSummary'),
};

let config = {};

// ── Initialize ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    checkHealth();
    updateApiUsageUI();

    // Init tsParticles
    tsParticles.load("tsparticles", {
        fpsLimit: 60,
        particles: {
            number: { value: 60, density: { enable: true, value_area: 800 } },
            color: { value: ["#22c55e", "#4ade80", "#3b82f6"] },
            shape: { type: "circle" },
            opacity: { value: 0.4, random: true, anim: { enable: true, speed: 1, opacity_min: 0.1, sync: false } },
            size: { value: 3, random: true, anim: { enable: true, speed: 2, size_min: 0.1, sync: false } },
            links: { enable: true, distance: 150, color: "#94a3b8", opacity: 0.3, width: 1 },
            move: { enable: true, speed: 1.5, direction: "none", random: true, straight: false, out_mode: "out", bounce: false, attract: { enable: false, rotateX: 600, rotateY: 1200 } }
        },
        interactivity: {
            detect_on: "canvas",
            events: {
                onhover: { enable: true, mode: "grab" },
                onclick: { enable: true, mode: "repulse" },
                resize: true
            },
            modes: {
                grab: { distance: 200, links: { opacity: 0.6 } },
                repulse: { distance: 250, duration: 0.4 }
            }
        },
        retina_detect: true
    });
});

// ── Health Check ──────────────────────────────────────────────────────────────

async function checkHealth() {
    try {
        const resp = await fetch(`${API_BASE}/health`);
        if (resp.ok) {
            el.serverStatus.textContent = 'Server online';
            el.statusDot.classList.add('online');
        }
    } catch {
        el.serverStatus.textContent = 'Server offline';
        el.statusDot.classList.remove('online');
    }
}

// ── API Usage Counter ─────────────────────────────────────────────────────────

function getTodayKey() {
    const d = new Date();
    return `bctc_usage_${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function getUsageCount() {
    return parseInt(localStorage.getItem(getTodayKey()) || '0', 10);
}

function incrementUsage(count = 1) {
    const key = getTodayKey();
    const current = parseInt(localStorage.getItem(key) || '0', 10);
    localStorage.setItem(key, current + count);
    updateApiUsageUI();
}

function updateApiUsageUI() {
    const used = getUsageCount();
    el.apiUsageText.textContent = `${used} / ${MAX_DAILY_REQUESTS}`;
    el.apiUsageBadge.classList.remove('warning', 'danger');
    if (used >= MAX_DAILY_REQUESTS) {
        el.apiUsageBadge.classList.add('danger');
    } else if (used >= 15) {
        el.apiUsageBadge.classList.add('warning');
    }
}

function canMakeRequests(count) {
    const used = getUsageCount();
    if (used + count > MAX_DAILY_REQUESTS) {
        const remaining = MAX_DAILY_REQUESTS - used;
        alert(`⚠️ Giới hạn API: Bạn chỉ còn ${remaining} lượt trích xuất hôm nay.\n\nBạn đang yêu cầu ${count} file nhưng chỉ còn ${remaining} lượt. Vui lòng giảm số file hoặc đợi sang ngày mai.`);
        return false;
    }
    return true;
}

// ── Navigation & Steps ────────────────────────────────────────────────────────

function showSection(id) {
    [el.formSection, el.uploadSection, el.progressSection, el.resultSection]
        .forEach(s => s.classList.add('hidden'));
    $(id).classList.remove('hidden');

    // Update step indicator
    const stepMap = { 'formSection': 1, 'uploadSection': 2, 'progressSection': 3, 'resultSection': 4 };
    const current = stepMap[id] || 1;
    el.stepsNav.querySelectorAll('.step-item').forEach(item => {
        const step = parseInt(item.dataset.step);
        item.classList.remove('active', 'done');
        if (step === current) item.classList.add('active');
        else if (step < current) item.classList.add('done');
    });
}

// ── Step 1: Config ────────────────────────────────────────────────────────────

el.form.addEventListener('submit', (e) => {
    e.preventDefault();
    config = {
        ticker: el.tickerInput.value.trim().toUpperCase(),
        period: el.periodType.value,
        from: parseInt(el.yearFrom.value),
        to: parseInt(el.yearTo.value),
    };

    if (config.from > config.to) {
        alert('Năm bắt đầu không được lớn hơn năm kết thúc.');
        return;
    }

    generateUploadInputs();
    showSection('uploadSection');
});

// ── Step 2: Upload ────────────────────────────────────────────────────────────

function generateUploadInputs() {
    el.uploadContainer.innerHTML = '';
    const periods = [];
    for (let y = config.from; y <= config.to; y++) {
        if (config.period === 'year') periods.push(String(y));
        else for (let q = 1; q <= 4; q++) periods.push(`${y}-Q${q}`);
    }

    periods.forEach(label => {
        const row = document.createElement('div');
        row.className = 'upload-row';
        row.innerHTML = `
            <div class="year-label">
                <i data-lucide="file-text"></i>
                ${label}
            </div>
            <input type="file" accept="application/pdf" class="pdf-input" data-period="${label}">
        `;
        el.uploadContainer.appendChild(row);
    });

    lucide.createIcons();
}

el.backToConfigBtn.addEventListener('click', () => showSection('formSection'));

// ── Step 3: AI Extraction ─────────────────────────────────────────────────────

async function warmupServer() {
    el.progressMessage.textContent = 'Đang kết nối server… (có thể mất 30-60s nếu server đang ngủ)';
    el.progressFill.style.width = '5%';
    el.progressText.textContent = '5%';
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 min timeout for warmup
        await fetch(`${API_BASE}/health`, { signal: controller.signal });
        clearTimeout(timeoutId);
    } catch (e) {
        throw new Error('Không thể kết nối tới server backend. Server có thể đang khởi động lại (Render Free Tier). Vui lòng đợi 1-2 phút rồi thử lại.');
    }
}

el.processAiBtn.addEventListener('click', async () => {
    const inputs = document.querySelectorAll('.pdf-input');
    const files = [];

    for (const input of inputs) {
        if (input.files.length > 0) {
            files.push({ period: input.dataset.period, file: input.files[0] });
        }
    }

    if (files.length === 0) {
        alert('Vui lòng chọn ít nhất 1 file PDF.');
        return;
    }

    // Check API usage limit
    if (!canMakeRequests(files.length)) return;

    showSection('progressSection');

    // Warmup: ping server to wake it up if it's sleeping (Render Free Tier)
    try {
        await warmupServer();
    } catch (err) {
        alert(err.message);
        showSection('uploadSection');
        return;
    }

    const allData = [];
    const total = files.length;

    for (let i = 0; i < total; i++) {
        const item = files[i];
        const pct = Math.round(((i + 0.5) / total) * 90) + 5; // 5% → 95%
        el.progressFill.style.width = `${pct}%`;
        el.progressText.textContent = `${pct}%`;
        el.progressMessage.textContent = `Đang trích xuất năm ${item.period}… (${i + 1}/${total})`;

        try {
            const fd = new FormData();
            fd.append('ticker', config.ticker);
            fd.append('year', item.period);
            fd.append('file', item.file);

            // 5-minute timeout per PDF (Gemini can take a while for large files)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 300000);

            const resp = await fetch(`${API_BASE}/api/jobs/extract-pdf`, {
                method: 'POST',
                body: fd,
                signal: controller.signal,
            });
            clearTimeout(timeoutId);

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Lỗi server');
            }

            const result = await resp.json();
            allData.push({ year: result.year, data: result.data });

            // Increment usage after each successful extraction
            incrementUsage(1);
        } catch (err) {
            const msg = err.name === 'AbortError'
                ? `Quá thời gian chờ (timeout 5 phút). Server hoặc Gemini API phản hồi quá chậm.`
                : err.message === 'Failed to fetch'
                    ? 'Mất kết nối tới server. Server Render (Free Tier) có thể đã ngủ. Vui lòng đợi 1-2 phút rồi thử lại.'
                    : err.message;
            alert(`Lỗi khi xử lý năm ${item.period}: ${msg}`);
            showSection('uploadSection');
            return;
        }
    }

    // Generate Excel
    el.progressFill.style.width = '95%';
    el.progressText.textContent = '95%';
    el.progressMessage.textContent = 'Đang tạo file Excel…';

    try {
        const resp = await fetch(`${API_BASE}/api/jobs/generate-excel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticker: config.ticker,
                year_from: config.from,
                year_to: config.to,
                yearly_data: allData,
            }),
        });

        if (!resp.ok) throw new Error('Lỗi khi tạo Excel');
        const data = await resp.json();

        el.progressFill.style.width = '100%';
        el.progressText.textContent = '100%';

        const downloadUrl = `${API_BASE}${data.download_url}`;
        await renderPreview(downloadUrl);

        el.resultSummary.textContent = `Đã trích xuất ${allData.length} năm cho ${config.ticker}`;
        showSection('resultSection');
        el.downloadBtn.onclick = () => window.open(downloadUrl, '_blank');
    } catch (err) {
        alert('Lỗi tạo Excel: ' + err.message);
        showSection('uploadSection');
    }
});

// ── Step 4: Result Preview ────────────────────────────────────────────────────

async function renderPreview(fileUrl) {
    const container = $('previewContainer');
    container.innerHTML = '<p style="padding:16px;color:var(--text-muted)">Đang tải preview…</p>';

    try {
        const resp = await fetch(fileUrl);
        const buf = await resp.arrayBuffer();
        const wb = XLSX.read(buf, { type: 'array' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const html = XLSX.utils.sheet_to_html(ws);

        const doc = new DOMParser().parseFromString(html, 'text/html');
        const table = doc.querySelector('table');

        if (table) {
            container.innerHTML = '';
            container.appendChild(table);
        }
    } catch {
        container.innerHTML = '<p style="padding:16px;color:var(--red-500)">Không thể load preview. Vui lòng tải file trực tiếp.</p>';
    }
}

el.newQueryBtn.addEventListener('click', () => {
    showSection('formSection');
    el.tickerInput.value = '';
});
