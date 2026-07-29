/**
 * Job Scraper Pro - Chrome Extension Popup Logic v2.0
 * Handles user interaction, scraping, Excel generation, warnings & logs
 */

// State
let scrapedData = [];
let extractionLog = [];

// DOM elements
const pageUrl = document.getElementById('pageUrl');
const pageTypeTag = document.getElementById('pageTypeTag');
const warningBanner = document.getElementById('warningBanner');
const warningText = document.getElementById('warningText');
const scrapeBtn = document.getElementById('scrapeBtn');
const statusArea = document.getElementById('statusArea');
const resultsArea = document.getElementById('resultsArea');
const resultCount = document.getElementById('resultCount');
const downloadBtn = document.getElementById('downloadBtn');
const dedupCheck = document.getElementById('dedupCheck');
const deepMode = document.getElementById('deepMode');
const autoDownload = document.getElementById('autoDownload');
const toggleSelectors = document.getElementById('toggleSelectors');
const selectorOptions = document.getElementById('selectorOptions');
const cssCompany = document.getElementById('cssCompany');
const cssRole = document.getElementById('cssRole');
const cssDesc = document.getElementById('cssDesc');
const logViewer = document.getElementById('logViewer');
const logToggle = document.getElementById('logToggle');
const logContent = document.getElementById('logContent');

// ─── Initialize ──────────────────────────────────────────────────────────

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const tab = tabs[0];
  if (tab && tab.url) {
    pageUrl.textContent = tab.url.length > 50
      ? tab.url.substring(0, 50) + '...'
      : tab.url;
    pageUrl.title = tab.url;
  } else {
    pageUrl.textContent = 'Could not detect page';
  }
});

// ─── Status helpers ──────────────────────────────────────────────────────

function showStatus(message, type = 'loading', details = '') {
  statusArea.className = `status ${type}`;

  let html = '';
  if (type === 'loading') {
    html = `<span class="spinner"></span> ${message}`;
  } else if (type === 'success') {
    html = `✅ ${message}`;
  } else if (type === 'error') {
    html = `❌ ${message}`;
    if (details) {
      html += `<br><small style="color:#666;">${details}</small>`;
    }
  } else if (type === 'warning') {
    html = `⚠️ ${message}`;
    if (details) {
      html += `<br><small style="color:#666;">${details}</small>`;
    }
  }
  statusArea.innerHTML = html;
  statusArea.style.display = 'block';
}

function hideStatus() {
  statusArea.style.display = 'none';
}

// ─── Page type tag ───────────────────────────────────────────────────────

function setPageTypeTag(type) {
  pageTypeTag.style.display = 'inline-block';
  pageTypeTag.className = `page-type-tag ${type}`;
  const labels = { job: '📄 Job Page', listing: '📋 Listing Page', unknown: '❓ Unknown' };
  pageTypeTag.textContent = labels[type] || type;
}

// ─── Warning banner ──────────────────────────────────────────────────────

function showWarning(message) {
  warningText.textContent = message;
  warningBanner.classList.add('show');
}

function hideWarning() {
  warningBanner.classList.remove('show');
}

// ─── Log viewer ──────────────────────────────────────────────────────────

function showLog(log) {
  extractionLog = log || [];
  logViewer.classList.add('show');
  logContent.textContent = extractionLog.join('\n');
}

function hideLog() {
  logViewer.classList.remove('show');
  logContent.textContent = '';
}

logToggle.addEventListener('click', () => {
  const isVisible = logContent.classList.contains('show');
  logContent.classList.toggle('show');
  logToggle.textContent = isVisible
    ? '📋 Show extraction log'
    : '📋 Hide extraction log';
});

// ─── Generate Excel ──────────────────────────────────────────────────────

function generateExcel(data) {
  if (!data || data.length === 0) {
    showStatus('No data to export', 'error');
    return;
  }

  const rows = [['S.No', 'Company Name', 'Job Role', 'Job Description', 'Source']];
  data.forEach((item, idx) => {
    const bullets = item.descriptionBullets && item.descriptionBullets.length > 0
      ? item.descriptionBullets.map(b => `• ${b}`).join('\n')
      : item.description || 'No description';
    rows.push([
      idx + 1,
      item.company || '',
      item.role || '',
      bullets,
      item.source || 'Extension'
    ]);
  });

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(rows);

  ws['!cols'] = [
    { wch: 6 },   // S.No
    { wch: 30 },  // Company
    { wch: 35 },  // Role
    { wch: 80 },  // Description
    { wch: 15 },  // Source
  ];

  XLSX.utils.book_append_sheet(wb, ws, 'Job Listings');

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
  const filename = `jobs_scraped_${timestamp}.xlsx`;
  XLSX.writeFile(wb, filename);

  return filename;
}

// ─── Scrape the page ─────────────────────────────────────────────────────

async function scrapePage() {
  hideStatus();
  hideWarning();
  hideLog();
  resultsArea.style.display = 'none';
  scrapedData = [];

  try {
    showStatus('Analyzing page content...', 'loading');

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      showStatus('Could not access this page', 'error');
      return;
    }

    if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('edge://')) {
      showStatus(
        'Cannot scrape browser internal pages',
        'error',
        'Try navigating to a job site first (e.g., naukri.com, indeed.com)'
      );
      return;
    }

    showStatus('Scanning page DOM for company/job data...', 'loading');

    const result = await chrome.tabs.sendMessage(tab.id, {
      action: 'scrape',
      options: {
        dedup: dedupCheck.checked,
        deepMode: deepMode.checked,
        cssSelectors: {
          company: cssCompany.value.trim(),
          role: cssRole.value.trim(),
          description: cssDesc.value.trim()
        }
      }
    });

    if (!result || result.error) {
      showStatus(
        'Scraping failed',
        'error',
        (result && result.error) || 'Could not communicate with the page. Try reloading the page.'
      );
      return;
    }

    // Show page type tag
    if (result.pageType) {
      setPageTypeTag(result.pageType);
    }

    // Show extraction log (always available)
    if (result.extractionLog && result.extractionLog.length > 0) {
      showLog(result.extractionLog);
    }

    // Show warning if listing page
    if (result.warning) {
      showWarning(result.warning);
    }

    scrapedData = result.data || [];

    if (scrapedData.length === 0) {
      showStatus(
        'No company/job data found',
        'error',
        !result.warning
          ? 'This page may not contain company or job listings.'
          : 'This appears to be a listing page. Try opening an individual job posting.'
      );
      return;
    }

    // Show results
    resultCount.textContent = scrapedData.length;
    resultsArea.style.display = 'block';

    // Check if data has placeholders
    const hasPlaceholders = scrapedData.some(
      d => (d.company || '').startsWith('[COMPANY_') || (d.role || '').startsWith('[ROLE_')
    );

    if (hasPlaceholders) {
      showStatus(
        `Found ${scrapedData.length} entries (with some missing data)`,
        'warning',
        'Some fields could not be extracted. Check the extraction log for details.'
      );
    } else {
      showStatus(
        `Found ${scrapedData.length} entries!`,
        'success'
      );
    }

    // Auto-download if enabled
    if (autoDownload.checked && scrapedData.length > 0) {
      try {
        const filename = generateExcel(scrapedData);
        showStatus(
          `Downloaded ${scrapedData.length} entries to Excel`,
          'success',
          `File: ${filename}`
        );
      } catch (err) {
        showStatus(
          'Data extracted! Click "Download Excel" to save.',
          hasPlaceholders ? 'warning' : 'success'
        );
      }
    }

  } catch (err) {
    console.error('Scrape error:', err);
    if (err.message && err.message.includes('Could not establish connection')) {
      showStatus(
        'Page not ready',
        'error',
        'Try reloading the page, then click the extension again.'
      );
    } else {
      showStatus(
        'Scraping failed',
        'error',
        err.message || 'An unexpected error occurred'
      );
    }
  }
}

// ─── Download button ─────────────────────────────────────────────────────

downloadBtn.addEventListener('click', async () => {
  if (scrapedData.length === 0) {
    showStatus('No data to download', 'error');
    return;
  }
  try {
    showStatus('Generating Excel file...', 'loading');
    const filename = generateExcel(scrapedData);
    showStatus(
      `Downloaded ${scrapedData.length} entries!`,
      'success',
      `File: ${filename}`
    );
  } catch (err) {
    showStatus(
      'Failed to generate Excel',
      'error',
      err.message
    );
  }
});

// ─── Toggle CSS selectors ────────────────────────────────────────────────

toggleSelectors.addEventListener('click', () => {
  const isVisible = selectorOptions.style.display !== 'none';
  selectorOptions.style.display = isVisible ? 'none' : 'block';
  toggleSelectors.textContent = isVisible
    ? '🎯 Show Custom CSS Selectors'
    : '🎯 Hide Custom CSS Selectors';
});

// ─── Scrape button ───────────────────────────────────────────────────────

scrapeBtn.addEventListener('click', scrapePage);
