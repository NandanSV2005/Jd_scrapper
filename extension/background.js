/**
 * Job Scraper Pro - Background Service Worker v3.0
 * Manages batch scraping: creates hidden tabs, scrapes job pages, reports progress.
 * Uses the user's real browser session so Naukri/Aggregator authenticate correctly.
 */

// ─── Batch State ──────────────────────────────────────────────────────────

const batchState = {
  urls: [],
  results: [],
  currentIndex: 0,
  totalCount: 0,
  isRunning: false,
  isCancelled: false,
  errors: [],
};

// ─── Utility ──────────────────────────────────────────────────────────────

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── Extension Installation ───────────────────────────────────────────────

chrome.runtime.onInstalled.addListener((details) => {
  console.log(`[Job Scraper] Extension ${details.reason === 'install' ? 'installed' : 'updated'}`);
});

// ─── Messaging ────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getPageInfo') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        sendResponse({ url: tabs[0].url, title: tabs[0].title });
      }
    });
    return true;
  }

  if (request.action === 'start-batch-scrape') {
    if (batchState.isRunning) {
      sendResponse({ error: 'Batch already in progress' });
      return;
    }
    startBatchScrape(request.urls).catch(err => console.error('[Batch] Fatal:', err));
    sendResponse({ started: true, total: request.urls.length });
    return false;
  }

  if (request.action === 'get-batch-status') {
    sendResponse({
      isRunning: batchState.isRunning,
      currentIndex: batchState.currentIndex,
      totalCount: batchState.totalCount,
      resultsCount: batchState.results.length,
      errors: batchState.errors.length,
      isCancelled: batchState.isCancelled,
    });
    return false;
  }

  if (request.action === 'cancel-batch-scrape') {
    batchState.isCancelled = true;
    sendResponse({ cancelled: true });
    return false;
  }
});

// ─── Batch Scrape Coordinator ─────────────────────────────────────────────

async function startBatchScrape(urls) {
  const validUrls = urls.filter(u => u && u.url && !u.url.startsWith('chrome://') && !u.url.startsWith('about:'));

  batchState.urls = validUrls;
  batchState.results = [];
  batchState.currentIndex = 0;
  batchState.totalCount = validUrls.length;
  batchState.isRunning = true;
  batchState.isCancelled = false;
  batchState.errors = [];

  notifyPopup('batch-started', { total: validUrls.length });

  for (let i = 0; i < validUrls.length; i++) {
    if (batchState.isCancelled) {
      console.log(`[Batch] Cancelled at index ${i}`);
      break;
    }

    batchState.currentIndex = i;
    const jobLink = validUrls[i];

    // Notify progress
    notifyPopup('batch-progress', {
      current: i + 1,
      total: validUrls.length,
      url: jobLink.url,
      company: jobLink.company || '',
      role: jobLink.role || '',
    });

    console.log(`[Batch] [${i + 1}/${validUrls.length}] ${jobLink.company || '?'} — ${(jobLink.role || '').substring(0, 60)}`);

    try {
      // Create a hidden tab to load the job page
      const tab = await createTab(jobLink.url);
      if (!tab || !tab.id) {
        batchState.errors.push({ url: jobLink.url, error: 'Failed to create tab' });
        continue;
      }

      // Wait for the tab to fully load (including JS rendering)
      const loaded = await waitForTabLoad(tab.id);
      if (!loaded) {
        batchState.errors.push({ url: jobLink.url, error: 'Tab load timeout' });
        safeCloseTab(tab.id);
        continue;
      }

      // Extra wait for dynamic content (JS-rendered job pages)
      await delay(2000);

      // Send scrape message to the tab's content script
      let result = await sendMessageToTab(tab.id, { action: 'scrape', options: { dedup: true, deepMode: true } });

      if (result && result.data && result.data.length > 0) {
        const item = result.data[0];
        // Enrich with listing card data if job page extraction was incomplete
        batchState.results.push({
          company: (item.company && !item.company.startsWith('[COMPANY_')) ? item.company : (jobLink.company || item.company || ''),
          role: (item.role && !item.role.startsWith('[ROLE_')) ? item.role : (jobLink.role || item.role || ''),
          description: item.description || '',
          descriptionBullets: item.descriptionBullets || [],
          skills: item.skills || [],
          highlights: item.highlights || '',
          location: item.location || '',
          experience: item.experience || '',
          education: item.education || '',
          employmentType: item.employmentType || '',
          department: item.department || '',
          industry: item.industry || '',
          source: item.source || 'batch',
        });
        const descLen = (item.description || '').length;
        console.log(`[Batch] [${i + 1}/${validUrls.length}] ✓ ${item.company} — ${descLen} chars in description`);
      } else {
        // Fallback: use listing card data (company + role only)
        if (jobLink.company) {
          batchState.results.push({
            company: jobLink.company,
            role: jobLink.role || '',
            description: '',
            descriptionBullets: [],
            skills: [],
            highlights: '',
            location: '',
            experience: '',
            education: '',
            employmentType: '',
            department: '',
            industry: '',
            source: 'batch-card-fallback',
          });
          console.log(`[Batch] [${i + 1}/${validUrls.length}] ⚠ Using listing card data (no extract): ${jobLink.company}`);
        } else {
          batchState.errors.push({ url: jobLink.url, error: 'No data extracted' });
          console.log(`[Batch] [${i + 1}/${validUrls.length}] ✗ No data`);
        }
      }

      // Close the tab
      safeCloseTab(tab.id);
    } catch (err) {
      console.error(`[Batch] Error:`, err);
      batchState.errors.push({ url: jobLink.url, error: err.message });
    }

    // Rate limiting between requests
    if (i < validUrls.length - 1 && !batchState.isCancelled) {
      await delay(1500 + Math.random() * 1000); // 1.5-2.5s delay to be nice to the server
    }
  }

  batchState.isRunning = false;
  console.log(`[Batch] Complete: ${batchState.results.length} entries`);

  // Notify popup
  notifyPopup('batch-complete', {
    totalUrls: validUrls.length,
    processedUrls: batchState.currentIndex + 1,
    resultsCount: batchState.results.length,
    errorsCount: batchState.errors.length,
    results: batchState.results,
    errors: batchState.errors,
  });
}

// ─── Tab Management ───────────────────────────────────────────────────────

function createTab(url) {
  return new Promise((resolve) => {
    chrome.tabs.create({ url, active: false }, (tab) => {
      resolve(tab);
    });
  });
}

function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    const TIMEOUT = 20000;
    let resolved = false;

    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(false);
      }
    }, TIMEOUT);

    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === 'complete' && !resolved) {
        resolved = true;
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        // Small extra wait for content script init
        setTimeout(() => resolve(true), 800);
      }
    }

    chrome.tabs.onUpdated.addListener(listener);

    // Safety timeout
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(false);
      }
    }, TIMEOUT + 2000);
  });
}

function sendMessageToTab(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message)
      .then(response => resolve(response))
      .catch(() => resolve(null));
  });
}

function safeCloseTab(tabId) {
  try {
    chrome.tabs.remove(tabId);
  } catch (e) {
    // Tab might already be closed
  }
}

// ─── Notify Popup ─────────────────────────────────────────────────────────

function notifyPopup(action, data) {
  chrome.runtime.sendMessage({ action, ...data }).catch(() => {
    // Popup might be closed — that's OK
  });
}
