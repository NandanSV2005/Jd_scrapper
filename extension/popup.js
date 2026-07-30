/**
 * Job Scraper Pro - Chrome Extension Popup v3.0
 * Handles: page type detection, batch scraping with progress, CSV export
 */

// ─── State ────────────────────────────────────────────────────────────────

let scrapedData = [];
let extractionLog = [];
let jobLinks = [];

// ─── DOM References ───────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const pageUrl = $('pageUrl');
const pageTypeTag = $('pageTypeTag');
const scrapeBtn = $('scrapeBtn');
const statusArea = $('statusArea');
const resultsArea = $('resultsArea');
const resultCount = $('resultCount');
const downloadBtn = $('downloadBtn');
const dedupCheck = $('dedupCheck');
const deepMode = $('deepMode');
const autoDownload = $('autoDownload');
const warningBanner = $('warningBanner');
const warningText = $('warningText');
const batchSection = $('batchSection');
const batchFoundCount = $('batchFoundCount');
const batchStartBtn = $('batchStartBtn');
const batchProgress = $('batchProgress');
const batchProgressText = $('batchProgressText');
const batchProgressBar = $('batchProgressBar');
const batchProgressCount = $('batchProgressCount');
const batchProgressStatus = $('batchProgressStatus');
const batchCancelBtn = $('batchCancelBtn');
const logViewer = $('logViewer');
const logToggle = $('logToggle');
const logContent = $('logContent');

// ─── Initialize ───────────────────────────────────────────────────────────

// Show current tab URL
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const tab = tabs[0];
  if (tab && tab.url) {
    pageUrl.textContent = tab.url.length > 60 ? tab.url.substring(0, 60) + '...' : tab.url;
    pageUrl.title = tab.url;
  }
});

// Check if batch is already running
chrome.runtime.sendMessage({ action: 'get-batch-status' }, (status) => {
  if (status && status.isRunning) {
    showBatchProgress({ current: status.currentIndex + 1, total: status.totalCount });
    hideAllSections();
    batchProgress.style.display = 'block';
  }
});

// Listen for background messages
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'batch-started') {
    showBatchProgress({ current: 0, total: message.total });
    batchProgressText.textContent = 'Starting batch scrape...';
  } else if (message.action === 'batch-progress') {
    const label = message.company || message.role || 'Job';
    batchProgressText.textContent = `Scraping: ${label.substring(0, 60)}`;
    showBatchProgress({ current: message.current, total: message.total });
  } else if (message.action === 'batch-complete') {
    onBatchComplete(message);
  }
});

// ─── UI Helpers ───────────────────────────────────────────────────────────

function hideAllSections() {
  hideStatus();
  hideWarning();
  hideLog();
  resultsArea.style.display = 'none';
  batchSection.style.display = 'none';
  batchProgress.style.display = 'none';
}

function showStatus(msg, type = 'loading', details = '') {
  statusArea.className = `status ${type}`;
  const icons = { loading: '<span class="spinner"></span>', success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  let html = `<span>${icons[type] || ''} ${msg}</span>`;
  if (details) html += `<br><small style="color:#666;">${details}</small>`;
  statusArea.innerHTML = html;
  statusArea.style.display = 'block';
}

function hideStatus() { statusArea.style.display = 'none'; }

function setPageTypeTag(type) {
  pageTypeTag.style.display = 'inline-block';
  pageTypeTag.className = `page-type-tag ${type}`;
  const labels = {
    job: '📄 Job Page',
    'listing-with-links': '📋 Listing (Batch Ready)',
    listing: '📋 Listing Page',
    unknown: '❓ Unknown',
  };
  pageTypeTag.textContent = labels[type] || type;
}

function showWarning(msg) {
  warningText.textContent = msg;
  warningBanner.classList.add('show');
}

function hideWarning() { warningBanner.classList.remove('show'); }

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
  const vis = logContent.classList.contains('show');
  logContent.classList.toggle('show');
  logToggle.textContent = vis ? '📋 Show extraction log' : '📋 Hide extraction log';
});

// ── Batch UI ────────────────────────────────────────────────────────────

function showBatchLinks(count) {
  batchFoundCount.textContent = count;
  batchSection.style.display = 'block';
  batchProgress.style.display = 'none';
}

function showBatchProgress(data) {
  const cur = data.current || 0;
  const tot = data.total || 1;
  const pct = Math.min(100, Math.round((cur / tot) * 100));
  batchProgressBar.style.width = `${pct}%`;
  batchProgressCount.textContent = `${cur} / ${tot}`;
  batchProgressStatus.textContent = cur >= tot ? '✓ Complete!' : `⏳ ${pct}%`;
  batchSection.style.display = 'none';
  batchProgress.style.display = 'block';
  batchCancelBtn.style.display = (cur < tot) ? 'block' : 'none';
}

function hideBatchUI() {
  batchSection.style.display = 'none';
  batchProgress.style.display = 'none';
}

function onBatchComplete(message) {
  batchProgressStatus.textContent = '✓ Complete!';
  batchProgressBar.style.width = '100%';
  batchProgressCount.textContent = `${message.totalUrls} / ${message.totalUrls}`;
  batchProgressText.textContent = `Finished! Got ${message.resultsCount} entries.`;
  batchCancelBtn.style.display = 'none';

  const allResults = message.results || [];
  if (allResults.length > 0) {
    scrapedData = allResults;
    resultCount.textContent = allResults.length;
    resultsArea.style.display = 'block';
    setPageTypeTag('job');
    showStatus(
      `✅ Batch complete: ${allResults.length} entries extracted`,
      'success',
      `${message.processedUrls} pages scraped, ${message.errorsCount} errors`
    );

    if (autoDownload.checked) {
      generateCSV(allResults);
    }
  } else {
    showStatus('No data extracted from any job page', 'error', `Tried ${message.processedUrls} pages.`);
  }
}

// ─── CSV Generation ───────────────────────────────────────────────────────

function generateCSV(data) {
  if (!data || data.length === 0) {
    showStatus('No data to export', 'error');
    return;
  }

  // Escape a field for CSV: wrap in quotes, escape inner quotes
  function esc(val) {
    if (val === null || val === undefined) return '';
    const s = String(val);
    // If it contains commas, newlines, or quotes, wrap in quotes
    if (s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  const headers = [
    'S.No', 'Company Name', 'Job Role',
    'Job Description (Bullet Points)', 'Key Skills',
    'Location', 'Experience', 'Education',
    'Employment Type', 'Department', 'Industry',
    'Source',
  ];

  const rows = [headers.map(esc).join(',')]; // CSV header row

  data.forEach((item, idx) => {
    // Format description as bullet points
    const descText = item.descriptionBullets && item.descriptionBullets.length > 0
      ? item.descriptionBullets.map(b => `• ${b}`).join('\n')
      : (item.description || '');

    const skillsText = item.skills && Array.isArray(item.skills)
      ? item.skills.join(', ')
      : '';

    const row = [
      idx + 1,
      item.company || '',
      item.role || '',
      descText,
      skillsText,
      item.location || '',
      item.experience || '',
      item.education || '',
      item.employmentType || '',
      item.department || '',
      item.industry || '',
      item.source || 'Extension',
    ];

    rows.push(row.map(esc).join(','));
  });

  const csvContent = '\uFEFF' + rows.join('\n'); // BOM for Excel UTF-8 support
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
  const filename = `jd_scraper_${timestamp}.csv`;

  chrome.downloads.download({
    url: url,
    filename: filename,
    saveAs: true,
  }, (downloadId) => {
    if (chrome.runtime.lastError) {
      // Fallback: use a download link
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
    }
    // Clean up after 1 minute
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  });

  showStatus(`✅ Downloaded ${data.length} entries as CSV!`, 'success',
    `File: ${filename} — Open in Excel/Google Sheets`);
}

// ─── Scrape Current Page ──────────────────────────────────────────────────

async function scrapePage() {
  hideAllSections();
  scrapedData = [];
  jobLinks = [];

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      showStatus('Could not access this page', 'error');
      return;
    }
    if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('edge://')) {
      showStatus('Cannot scrape browser internal pages', 'error',
        'Try navigating to naukri.com job listing page first.');
      return;
    }

    showStatus('Scanning page for job data...', 'loading');

    const result = await chrome.tabs.sendMessage(tab.id, {
      action: 'scrape',
      options: { dedup: dedupCheck.checked, deepMode: deepMode.checked },
    });

    if (!result || result.error) {
      showStatus('Scraping failed', 'error',
        (result && result.error) || 'Could not communicate with page. Try reloading.');
      return;
    }

    // Show page type & log
    if (result.pageType) setPageTypeTag(result.pageType);
    if (result.extractionLog && result.extractionLog.length > 0) showLog(result.extractionLog);

    // ── Listing page with job links → batch option ──
    if (result.pageType === 'listing-with-links' && result.jobLinks && result.jobLinks.length > 0) {
      jobLinks = result.jobLinks;
      showStatus(`Found ${result.jobLinks.length} job listing(s)`, 'success',
        'Click "Batch Scrape All" to visit each job page and extract full details.');
      showBatchLinks(result.jobLinks.length);
      return;
    }

    // ── Listing page without links → warning ──
    if (result.pageType === 'listing' && (!result.jobLinks || result.jobLinks.length === 0)) {
      showStatus('No job listings found on this page', 'error');
      showWarning('Could not find recognizable job cards. Try a different search results page.');
      return;
    }

    // ── Individual job page → show results ──
    scrapedData = result.data || [];
    if (scrapedData.length === 0) {
      showStatus('No data found', 'error',
        'Try navigating to a Naukri job search page (e.g., naukri.com/ai-jobs)');
      return;
    }

    resultCount.textContent = scrapedData.length;
    resultsArea.style.display = 'block';
    showStatus(`Found ${scrapedData.length} entry`, 'success');

    if (autoDownload.checked && scrapedData.length > 0) {
      generateCSV(scrapedData);
    }

  } catch (err) {
    console.error('Scrape error:', err);
    showStatus('Scraping failed', 'error',
      err.message?.includes('Could not establish connection')
        ? 'Try reloading the page, then click the extension again.'
        : err.message || 'An unexpected error occurred');
  }
}

// ─── Batch Handlers ───────────────────────────────────────────────────────

async function startBatchScrape() {
  if (jobLinks.length === 0) {
    showStatus('No job links to process', 'error');
    return;
  }

  showBatchProgress({ current: 0, total: jobLinks.length });
  batchProgressText.textContent = 'Starting batch scrape...';
  batchCancelBtn.style.display = 'block';

  chrome.runtime.sendMessage({
    action: 'start-batch-scrape',
    urls: jobLinks,
  }, (response) => {
    if (response && response.error) {
      showStatus(response.error, 'error');
      hideBatchUI();
    }
  });
}

function cancelBatchScrape() {
  chrome.runtime.sendMessage({ action: 'cancel-batch-scrape' });
  batchProgressText.textContent = '⏹ Cancelling...';
  batchCancelBtn.disabled = true;
  batchCancelBtn.textContent = '⏹ Cancelling...';
}

// ─── Event Listeners ──────────────────────────────────────────────────────

scrapeBtn.addEventListener('click', scrapePage);

downloadBtn.addEventListener('click', () => {
  if (scrapedData.length === 0) {
    showStatus('No data to download', 'error');
    return;
  }
  generateCSV(scrapedData);
});

batchStartBtn.addEventListener('click', startBatchScrape);
batchCancelBtn.addEventListener('click', cancelBatchScrape);
