/**
 * BCTC Crawler – Frontend Application
 * ====================================
 * Handles form submission, job polling, and file download.
 */

// ── Configuration ─────────────────────────────────────────────────────────────

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://bctc-crawler-api.onrender.com';  // Update after Render deploy

const POLL_INTERVAL_MS = 3000;

// ── DOM Elements ──────────────────────────────────────────────────────────────

const elements = {
    form: document.getElementById('bctcForm'),
    tickerInput: document.getElementById('tickerInput'),
    tickerTags: document.getElementById('tickerTags'),
    reportType: document.getElementById('reportType'),
    periodType: document.getElementById('periodType'),
    yearFrom: document.getElementById('yearFrom'),
    yearTo: document.getElementById('yearTo'),
    submitBtn: document.getElementById('submitBtn'),
    serverStatus: document.getElementById('serverStatus'),
    statusDot: document.querySelector('.status-dot'),

    formSection: document.getElementById('formSection'),
    progressSection: document.getElementById('progressSection'),
    resultSection: document.getElementById('resultSection'),
    errorSection: document.getElementById('errorSection'),

    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    progressMessage: document.getElementById('progressMessage'),
    progressSteps: document.getElementById('progressSteps'),

    downloadBtn: document.getElementById('downloadBtn'),
    newQueryBtn: document.getElementById('newQueryBtn'),
    resultMessage: document.getElementById('resultMessage'),

    retryBtn: document.getElementById('retryBtn'),
    errorMessage: document.getElementById('errorMessage'),
};

// ── State ─────────────────────────────────────────────────────────────────────

let currentJobId = null;
let pollTimer = null;
let tickers = [];

// ── Health Check ──────────────────────────────────────────────────────────────

async function checkHealth() {
    try {
        const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
        if (resp.ok) {
            elements.serverStatus.textContent = 'Server online';
            elements.statusDot.classList.add('online');
            return true;
        }
    } catch (e) {
        // Server not reachable
    }
    elements.serverStatus.textContent = 'Server offline';
    elements.statusDot.classList.remove('online');
    return false;
}

// Run health check on load and every 30s
checkHealth();
setInterval(checkHealth, 30000);

// ── Ticker Tags ───────────────────────────────────────────────────────────────

function renderTags() {
    elements.tickerTags.innerHTML = tickers
        .map((t, i) => `
            <span class="ticker-tag">
                ${t}
                <span class="remove" data-index="${i}">×</span>
            </span>
        `).join('');

    // Attach remove handlers
    elements.tickerTags.querySelectorAll('.remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.target.dataset.index);
            tickers.splice(idx, 1);
            renderTags();
        });
    });
}

elements.tickerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        addTickersFromInput();
    }
});

elements.tickerInput.addEventListener('blur', addTickersFromInput);

function addTickersFromInput() {
    const val = elements.tickerInput.value.trim();
    if (!val) return;

    const newTickers = val.split(/[,;\s]+/)
        .map(t => t.trim().toUpperCase())
        .filter(t => t.length > 0 && t.length <= 10 && !tickers.includes(t));

    tickers = [...tickers, ...newTickers].slice(0, 10);
    elements.tickerInput.value = '';
    renderTags();
}

// ── Section Visibility ────────────────────────────────────────────────────────

function showSection(sectionId) {
    ['formSection', 'progressSection', 'resultSection', 'errorSection'].forEach(id => {
        elements[id].classList.toggle('hidden', id !== sectionId);
    });
}

// ── Form Submission ───────────────────────────────────────────────────────────

elements.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    addTickersFromInput();  // Catch any remaining input

    if (tickers.length === 0) {
        alert('Vui lòng nhập ít nhất 1 mã cổ phiếu.');
        return;
    }

    const yearFrom = parseInt(elements.yearFrom.value);
    const yearTo = parseInt(elements.yearTo.value);

    if (yearTo < yearFrom) {
        alert('Năm kết thúc phải >= năm bắt đầu.');
        return;
    }

    const payload = {
        tickers: tickers,
        report_type: elements.reportType.value,
        period: elements.periodType.value,
        year_from: yearFrom,
        year_to: yearTo,
    };

    try {
        elements.submitBtn.disabled = true;
        elements.submitBtn.textContent = '⏳ Đang gửi...';

        const resp = await fetch(`${API_BASE}/api/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Lỗi tạo job');
        }

        const data = await resp.json();
        currentJobId = data.job_id;

        // Switch to progress view
        showSection('progressSection');
        updateSteps(0);
        startPolling();

    } catch (err) {
        showError(err.message);
    } finally {
        elements.submitBtn.disabled = false;
        elements.submitBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Trích xuất & Tải Excel
        `;
    }
});

// ── Polling ───────────────────────────────────────────────────────────────────

function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollJobStatus, POLL_INTERVAL_MS);
    pollJobStatus();  // Immediate first poll
}

async function pollJobStatus() {
    if (!currentJobId) return;

    try {
        const resp = await fetch(`${API_BASE}/api/jobs/${currentJobId}`);
        if (!resp.ok) throw new Error('Không thể lấy trạng thái job');

        const data = await resp.json();

        // Update progress UI
        elements.progressFill.style.width = `${data.progress}%`;
        elements.progressText.textContent = `${data.progress}%`;
        elements.progressMessage.textContent = data.message;

        // Update steps
        if (data.progress < 10) updateSteps(0);
        else if (data.progress < 40) updateSteps(1);
        else if (data.progress < 80) updateSteps(2);
        else if (data.progress < 100) updateSteps(3);
        else updateSteps(4);

        // Check completion
        if (data.status === 'completed') {
            clearInterval(pollTimer);
            showResult(data);
        } else if (data.status === 'failed') {
            clearInterval(pollTimer);
            showError(data.message || data.error || 'Job thất bại');
        }

    } catch (err) {
        console.error('Poll error:', err);
    }
}

function updateSteps(activeIndex) {
    const steps = elements.progressSteps.querySelectorAll('.step');
    steps.forEach((step, i) => {
        step.classList.remove('active', 'completed');
        if (i < activeIndex) step.classList.add('completed');
        else if (i === activeIndex) step.classList.add('active');
    });
}

// ── Result ────────────────────────────────────────────────────────────────────

function showResult(data) {
    showSection('resultSection');
    elements.resultMessage.textContent = data.message || 'File Excel đã sẵn sàng!';

    elements.downloadBtn.onclick = () => {
        window.open(`${API_BASE}${data.download_url}`, '_blank');
    };
}

elements.newQueryBtn.addEventListener('click', resetToForm);

// ── Error ─────────────────────────────────────────────────────────────────────

function showError(message) {
    showSection('errorSection');
    elements.errorMessage.textContent = message;
}

elements.retryBtn.addEventListener('click', resetToForm);

// ── Reset ─────────────────────────────────────────────────────────────────────

function resetToForm() {
    currentJobId = null;
    if (pollTimer) clearInterval(pollTimer);
    elements.progressFill.style.width = '0%';
    elements.progressText.textContent = '0%';
    showSection('formSection');
}
