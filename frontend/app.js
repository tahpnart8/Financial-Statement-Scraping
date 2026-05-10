/**
 * BCTC AI Crawler - AI PDF Orchestrator
 */

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8002'
    : 'https://bctc-crawler-api.onrender.com';

const elements = {
    form: document.getElementById('bctcForm'),
    tickerInput: document.getElementById('tickerInput'),
    periodType: document.getElementById('periodType'),
    yearFrom: document.getElementById('yearFrom'),
    yearTo: document.getElementById('yearTo'),
    
    uploadSection: document.getElementById('uploadSection'),
    formSection: document.getElementById('formSection'),
    progressSection: document.getElementById('progressSection'),
    resultSection: document.getElementById('resultSection'),
    
    uploadContainer: document.getElementById('uploadContainer'),
    processAiBtn: document.getElementById('processAiBtn'),
    backToConfigBtn: document.getElementById('backToConfigBtn'),
    
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    progressMessage: document.getElementById('progressMessage'),
    
    previewTableHeader: document.getElementById('previewTableHeader'),
    previewTableBody: document.getElementById('previewTableBody'),
    downloadBtn: document.getElementById('downloadBtn'),
    newQueryBtn: document.getElementById('newQueryBtn'),
    
    serverStatus: document.getElementById('serverStatus'),
    statusDot: document.querySelector('.status-dot'),
};

let config = {};
let uploadedFilesMap = {};

// --- Health Check ---
async function checkHealth() {
    try {
        const resp = await fetch(`${API_BASE}/health`);
        if (resp.ok) {
            elements.serverStatus.textContent = 'Server online';
            elements.statusDot.classList.add('online');
        }
    } catch (e) {
        elements.serverStatus.textContent = 'Server offline';
        elements.statusDot.classList.remove('online');
    }
}
checkHealth();

// --- Navigation ---
function showSection(id) {
    elements.formSection.classList.add('hidden');
    if (elements.uploadSection) elements.uploadSection.classList.add('hidden');
    elements.progressSection.classList.add('hidden');
    elements.resultSection.classList.add('hidden');
    document.getElementById(id).classList.remove('hidden');
}

// --- Step 1: Config ---
elements.form.addEventListener('submit', (e) => {
    e.preventDefault();
    config = {
        ticker: elements.tickerInput.value.trim().toUpperCase(),
        period: elements.periodType.value,
        from: parseInt(elements.yearFrom.value),
        to: parseInt(elements.yearTo.value)
    };
    
    generateUploadInputs();
    showSection('uploadSection');
});

function generateUploadInputs() {
    elements.uploadContainer.innerHTML = '';
    uploadedFilesMap = {};
    const years = [];
    for (let y = config.from; y <= config.to; y++) {
        if (config.period === 'year') years.push(y);
        else {
            for (let q = 1; q <= 4; q++) years.push(`${y}-Q${q}`);
        }
    }
    
    years.forEach(periodLabel => {
        const div = document.createElement('div');
        div.className = 'form-group';
        div.style.marginBottom = '15px';
        div.style.padding = '10px';
        div.style.border = '1px dashed var(--border-color)';
        div.style.borderRadius = '8px';
        div.style.background = '#f8fafc';
        
        div.innerHTML = `
            <label style="font-size: 0.9rem; color: var(--accent-primary); font-weight: bold;">Tải BCTC PDF năm ${periodLabel}:</label>
            <input type="file" accept="application/pdf" class="pdf-file-input" data-period="${periodLabel}" style="width: 100%; border: none; background: transparent; padding: 5px 0;">
        `;
        elements.uploadContainer.appendChild(div);
    });
}

if (elements.backToConfigBtn) {
    elements.backToConfigBtn.addEventListener('click', () => showSection('formSection'));
}

// --- Step 2: Orchestrator ---
if (elements.processAiBtn) {
    elements.processAiBtn.addEventListener('click', async () => {
        const fileInputs = document.querySelectorAll('.pdf-file-input');
        const filesToProcess = [];
        
        for (let input of fileInputs) {
            if (input.files.length > 0) {
                filesToProcess.push({
                    period: input.dataset.period,
                    file: input.files[0]
                });
            }
        }

        if (filesToProcess.length === 0) {
            alert('Vui lòng chọn ít nhất 1 file PDF.');
            return;
        }

        showSection('progressSection');
        const allExtractedData = [];
        const total = filesToProcess.length;

        // Hành trình cuốn chiếu: Xử lý từng file một để tránh sập Server Vercel
        for (let i = 0; i < total; i++) {
            const item = filesToProcess[i];
            
            // Cập nhật Progress
            const pct = Math.round((i / total) * 100);
            elements.progressFill.style.width = `${pct}%`;
            elements.progressText.textContent = `${pct}%`;
            elements.progressMessage.textContent = `Đang trích xuất AI cho năm ${item.period}... (File ${i+1}/${total})`;
            
            try {
                const formData = new FormData();
                formData.append("ticker", config.ticker);
                formData.append("year", item.period);
                formData.append("file", item.file);

                const resp = await fetch(`${API_BASE}/api/jobs/extract-pdf`, {
                    method: 'POST',
                    body: formData
                });

                if (!resp.ok) {
                    const err = await resp.json();
                    throw new Error(err.detail || "Lỗi server");
                }

                const result = await resp.json();
                allExtractedData.push({
                    year: result.year,
                    data: result.data
                });

            } catch (err) {
                alert(`Lỗi khi xử lý năm ${item.period}: ` + err.message);
                showSection('uploadSection');
                return; // Dừng lại nếu có lỗi
            }
        }

        // Bước 2: Gom toàn bộ kết quả, gọi API tạo Excel
        elements.progressFill.style.width = `95%`;
        elements.progressText.textContent = `95%`;
        elements.progressMessage.textContent = `Đang tổng hợp dữ liệu và tạo file Excel...`;

        try {
            const excelResp = await fetch(`${API_BASE}/api/jobs/generate-excel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: config.ticker,
                    year_from: config.from,
                    year_to: config.to,
                    yearly_data: allExtractedData
                })
            });

            if (!excelResp.ok) throw new Error("Lỗi khi tạo Excel");
            const excelData = await excelResp.json();
            
            elements.progressFill.style.width = `100%`;
            elements.progressText.textContent = `100%`;
            
            await renderPreviewExcel(`${API_BASE}${excelData.download_url}`);
            
            showSection('resultSection');
            elements.downloadBtn.onclick = () => window.open(`${API_BASE}${excelData.download_url}`, '_blank');
            
        } catch (err) {
            alert('Lỗi tạo Excel: ' + err.message);
            showSection('uploadSection');
        }
    });
}

// --- Step 3: Result & SheetJS Preview ---
async function renderPreviewExcel(fileUrl) {
    try {
        elements.previewTableHeader.innerHTML = "";
        elements.previewTableBody.innerHTML = "<tr><td style='padding:10px;'>Đang load Excel Preview...</td></tr>";
        
        // Fetch file blob
        const response = await fetch(fileUrl);
        const arrayBuffer = await response.arrayBuffer();
        
        // Parse bằng SheetJS
        const workbook = XLSX.read(arrayBuffer, { type: 'array' });
        
        // Lấy Sheet đầu tiên (BCTC du phong)
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        
        // Convert to HTML string
        const htmlStr = XLSX.utils.sheet_to_html(worksheet);
        
        // Dùng trick để extract the <table> từ htmlStr và dán vào
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlStr, 'text/html');
        const generatedTable = doc.querySelector('table');
        
        if (generatedTable) {
            // Apply style for SheetJS generated table
            generatedTable.style.width = "100%";
            generatedTable.style.borderCollapse = "collapse";
            
            const tds = generatedTable.querySelectorAll('td, th');
            tds.forEach(td => {
                td.style.border = "1px solid #e2e8f0";
                td.style.padding = "6px";
                td.style.whiteSpace = "nowrap";
            });
            
            const tableContainer = document.querySelector('.preview-container');
            tableContainer.innerHTML = "";
            tableContainer.appendChild(generatedTable);
        }
        
    } catch (e) {
        console.error("Lỗi preview Excel:", e);
        elements.previewTableBody.innerHTML = "<tr><td style='padding:10px; color:red'>Không thể load Preview, vui lòng tải file trực tiếp!</td></tr>";
    }
}

elements.newQueryBtn.addEventListener('click', () => {
    showSection('formSection');
    elements.tickerInput.value = '';
});
