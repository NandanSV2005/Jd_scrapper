/**
 * Job Scraper Pro - Chrome Extension Popup v3.0
 * Handles user interaction, single page scraping, batch mode with progress
 */

// State
let scrapedData = [];
let extractionLog = [];
let jobLinks = [];

// DOM elements - General
const pageUrl = document.getElementById('pageUrl');
const pageTypeTag = document.getElementById('pageTypeTag');
const scrapeBtn = document.getElementById('scrapeBtn');
const statusArea = document.getElementById('statusArea');
const resultsArea = document.getElementById('resultsArea');
const resultCount = document.getElementById('resultCount');
const downloadBtn = document.getElementById('downloadBtn');

// DOM elements - Options
const dedupCheck = document.getElementById('dedupCheck');
const deepMode = document.getElementById('deepMode');
const autoDownload = document.getElementById('autoDownload');
const toggleSelectors = document.getElementById('toggleSelectors');
const selectorOptions = document.getElementById('selectorOptions');
const cssCompany = document.getElementById('cssCompany');
const cssRole = document.getElementById('cssRole');
const cssDesc = document.getElementById('cssDesc');

// DOM elements - Warning
const warningBanner = document.getElementById('warningBanner');
const warningText = document.getElementById('warningText');

// DOM elements - Batch
const batchSection = document.getElementById('batchSection');
const batchFoundCount = document.getElementById('batchFoundCount');
const batchStartBtn = document.getElementById('batchStartBtn');
const batchProgress = document.getElementById('batchProgress');
const batchProgressText = document.getElementById('batchProgressText');
const batchProgressBar = document.getElementById('batchProgressBar');
const batchProgressCount = document.getElementById('batchProgressCount');
const batchProgressStatus = document.getElementById('batchProgressStatus');
const batchCancelBtn = document.getElementById('batchCancelBtn');

// DOM elements - Log
const logViewer = document.getElementById('logViewer');
const logToggle = document.getElementById('logToggle');
const logContent = document.getElementById('logContent');

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZE
// ═══════════════════════════════════════════════════════════════════════════

// Get current tab URL
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

// Check if batch is already running from a previous popup session
chrome.runtime.sendMessage({ action: 'get-batch-status' }, (status) => {
  if (status && status.isRunning) {
    showBatchProgress({
      current: status.currentIndex + 1,
      total: status.totalCount,
    });
    hideAllSections();
    batchProgress.style.display = 'block';
  }
});

// Listen for messages from background.js (batch progress updates)
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'batch-started') {
    showBatchProgress({ current: 0, total: message.total });
    batchProgressText.textContent = 'Starting batch scrape...';
  } else if (message.action === 'batch-progress') {
    batchProgressText.textContent = `Scraping: ${message.company || 'Job'} — ${(message.role || message.url || '').substring(0, 50)}`;
    showBatchProgress({ current: message.current, total: message.total });
  } else if (message.action === 'batch-complete') {
    batchProgressStatus.textContent = '✓ Complete!';
    batchProgressBar.style.width = '100%';
    batchProgressCount.textContent = `${message.totalUrls} / ${message.totalUrls}`;
    batchProgressText.textContent = `Finished! Got ${message.resultsCount} entries.`;
    batchCancelBtn.style.display = 'none';

    // Show results
    const allResults = message.results || [];
    if (allResults.length > 0) {
      scrapedData = allResults;
      resultCount.textContent = allResults.length;
      resultsArea.style.display = 'block';
      showLog(allResults.slice(0, 5).map(r => `✓ ${r.company || '?'} — ${(r.role || '').substring(0, 60)}`));
      setPageTypeTag('job');

      showStatus(
        `✅ Batch complete: ${allResults.length} entries extracted`,
        'success',
        `${message.processedUrls} pages scraped, ${message.errorsCount} errors`
      );

      if (autoDownload.checked) {
        try {
          generateExcel(allResults);
        } catch (e) { /* download button is still available */ }
      }
    } else {
      showStatus(
        'No data extracted from any job page',
        'error',
        `Tried ${message.processedUrls} pages. Check the extraction log.`
      );
    }
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function hideAllSections() {
  hideStatus();
  hideWarning();
  hideLog();
  resultsArea.style.display = 'none';
  batchSection.style.display = 'none';
  batchProgress.style.display = 'none';
}

function showStatus(message, type = 'loading', details = '') {
  statusArea.className = `status ${type}`;
  let html = '';
  if (type === 'loading') html = `<span class="spinner"></span> ${message}`;
  else if (type === 'success') html = `✅ ${message}`;
  else if (type === 'error') html = `❌ ${message}`;
  else if (type === 'warning') html = `⚠️ ${message}`;
  if (details) html += `<br><small style="color:#666;">${details}</small>`;
  statusArea.innerHTML = html;
  statusArea.style.display = 'block';
}

function hideStatus() { statusArea.style.display = 'none'; }

function setPageTypeTag(type) {
  pageTypeTag.style.display = 'inline-block';
  pageTypeTag.className = `page-type-tag ${type}`;
  const labels = { job: '📄 Job Page', 'listing-with-links': '📋 Listing (Batch Ready)', listing: '📋 Listing Page', unknown: '❓ Unknown' };
  pageTypeTag.textContent = labels[type] || type;
}

function showWarning(message) {
  warningText.textContent = message;
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
  const isVisible = logContent.classList.contains('show');
  logContent.classList.toggle('show');
  logToggle.textContent = isVisible ? '📋 Show extraction log' : '📋 Hide extraction log';
});

// ── Batch UI ────────────────────────────────────────────────────────────

function showBatchLinks(count) {
  batchFoundCount.textContent = count;
  batchSection.style.display = 'block';
  batchProgress.style.display = 'none';
}

function showBatchProgress(data) {
  const current = data.current || 0;
  const total = data.total || 1;
  const pct = Math.min(100, Math.round((current / total) * 100));
  batchProgressBar.style.width = `${pct}%`;
  batchProgressCount.textContent = `${current} / ${total}`;
  batchProgressStatus.textContent = current >= total ? '✓ Complete!' : `⏳ ${pct}%`;
  batchSection.style.display = 'none';
  batchProgress.style.display = 'block';
  batchCancelBtn.style.display = (current < total) ? 'block' : 'none';
}

function hideBatchUI() {
  batchSection.style.display = 'none';
  batchProgress.style.display = 'none';
}

// ═══════════════════════════════════════════════════════════════════════════
// EXCEL GENERATION
// ═══════════════════════════════════════════════════════════════════════════

function generateExcel(data) {
  if (!data || data.length === 0) {
    showStatus('No data to export', 'error');
    return;
  }

  const rows = [[
    'S.No', 'Company Name', 'Job Role',
    'Job Description (Bullet Points)', 'Key Skills',
    'Location', 'Experience', 'Education',
    'Employment Type', 'Department', 'Industry',
    'Job Highlights', 'Source'
  ]];

  data.forEach((item, idx) => {
    // Format description as bullet points on separate lines
    const descBullets = item.descriptionBullets && item.descriptionBullets.length > 0
      ? item.descriptionBullets.map(b => `• ${b}`).join('\n')
      : item.description || 'No description';

    // Format skills as comma-separated
    const skillsStr = item.skills && Array.isArray(item.skills) && item.skills.length > 0
      ? item.skills.join(', ')
      : '';

    rows.push([
      idx + 1,
      item.company || '',
      item.role || '',
      descBullets,
      skillsStr,
      item.location || '',
      item.experience || '',
      item.education || '',
      item.employmentType || '',
      item.department || '',
      item.industry || '',
      item.highlights || '',
      item.source || 'Extension'
    ]);
  });

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(rows);

  // Set column widths
  ws['!cols'] = [
    { wch: 6 },   // S.No
    { wch: 30 },  // Company
    { wch: 35 },  // Job Role
    { wch: 80 },  // Description (wider for bullets)
    { wch: 35 },  // Key Skills
    { wch: 20 },  // Location
    { wch: 15 },  // Experience
    { wch: 25 },  // Education
    { wch: 18 },  // Employment Type
    { wch: 25 },  // Department
    { wch: 25 },  // Industry
    { wch: 50 },  // Job Highlights
    { wch: 15 },  // Source
  ];

  // Enable text wrapping on description and highlights columns
  // so bullet points show on separate lines
  if (!ws['!rows']) ws['!rows'] = [];
  for (let i = 0; i <= data.length; i++) {
    if (!ws['!rows'][i]) ws['!rows'][i] = {};
    ws['!rows'][i].hpx = 20; // default row height
  }
  // Set taller row height for data rows with long descriptions
  for (let i = 1; i <= data.length; i++) {
    const item = data[i - 1];
    const bulletCount = (item.descriptionBullets && item.descriptionBullets.length) || 0;
    if (bulletCount > 10) {
      if (!ws['!rows'][i]) ws['!rows'][i] = {};
      ws['!rows'][i].hpx = Math.min(400, bulletCount * 18);
    } else if (bulletCount > 3) {
      if (!ws['!rows'][i]) ws['!rows'][i] = {};
      ws['!rows'][i].hpx = 120;
    }
  }

  XLSX.utils.book_append_sheet(wb, ws, 'Job Listings');

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
  const filename = `jd_scraper_${timestamp}.xlsx`;
  XLSX.writeFile(wb, filename);
  return filename;
}

// ═══════════════════════════════════════════════════════════════════════════
// SCRAPE THIS PAGE
// ═══════════════════════════════════════════════════════════════════════════

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
        'Try navigating to a job site first (e.g., naukri.com, indeed.com)');
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
      showStatus('Scraping failed', 'error',
        (result && result.error) || 'Could not communicate with the page. Try reloading.');
      return;
    }

    // Show page type
    if (result.pageType) setPageTypeTag(result.pageType);

    // Show extraction log
    if (result.extractionLog && result.extractionLog.length > 0) showLog(result.extractionLog);

    // ── LISTING PAGE WITH JOB LINKS → Show Batch Option ──────────────
    if (result.pageType === 'listing-with-links' && result.jobLinks && result.jobLinks.length > 0) {
      jobLinks = result.jobLinks;
      showStatus(`Found ${result.jobLinks.length} job listing(s) on this page`, 'success',
        'Click "Batch Scrape All Jobs" to auto-crawl each one for full details.');
      showBatchLinks(result.jobLinks.length);
      return;
    }

    // ── LISTING PAGE WITHOUT LINKS → Show Warning ────────────────────
    if (result.pageType === 'listing' && (!result.jobLinks || result.jobLinks.length === 0)) {
      showStatus('No job listings found on this page', 'error',
        'Could not find recognizable job cards. Try a different search results page.');
      showWarning('No job listing links could be extracted from this page. ' +
        'This may be a different type of page.');
      return;
    }

    // ── INDIVIDUAL JOB PAGE → Show Results Normally ─────────────────
    scrapedData = result.data || [];

    if (scrapedData.length === 0) {
      showStatus('No data found', 'error',
        'Try navigating to a job page or search results page.');
      return;
    }

    resultCount.textContent = scrapedData.length;
    resultsArea.style.display = 'block';

    const hasPlaceholders = scrapedData.some(
      d => (d.company || '').startsWith('[COMPANY_') || (d.role || '').startsWith('[ROLE_')
    );

    showStatus(
      `Found ${scrapedData.length} entries`,
      hasPlaceholders ? 'warning' : 'success',
      hasPlaceholders ? 'Some fields could not be extracted. Check the log.' : ''
    );

    if (autoDownload.checked && scrapedData.length > 0) {
      try { generateExcel(scrapedData); } catch (e) {}
    }

  } catch (err) {
    console.error('Scrape error:', err);
    showStatus('Scraping failed', 'error',
      err.message?.includes('Could not establish connection')
        ? 'Try reloading the page, then click the extension again.'
        : err.message || 'An unexpected error occurred');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// BATCH SCRAPE HANDLERS
// ═══════════════════════════════════════════════════════════════════════════

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

// ═══════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════════════

// Scrape button
scrapeBtn.addEventListener('click', scrapePage);

// Download button
downloadBtn.addEventListener('click', async () => {
  if (scrapedData.length === 0) {
    showStatus('No data to download', 'error');
    return;
  }
  try {
    showStatus('Generating Excel file...', 'loading');
    generateExcel(scrapedData);
    showStatus(`Downloaded ${scrapedData.length} entries!`, 'success');
  } catch (err) {
    showStatus('Failed to generate Excel', 'error', err.message);
  }
});

// Batch buttons
batchStartBtn.addEventListener('click', startBatchScrape);
batchCancelBtn.addEventListener('click', cancelBatchScrape);

// CSS selector toggle
toggleSelectors.addEventListener('click', () => {
  const isVisible = selectorOptions.style.display !== 'none';
  selectorOptions.style.display = isVisible ? 'none' : 'block';
  toggleSelectors.textContent = isVisible
    ? '🎯 Show Custom CSS Selectors'
    : '🎯 Hide Custom CSS Selectors';
});
