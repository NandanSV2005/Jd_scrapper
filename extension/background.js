/**
 * Job Scraper Pro - Background Service Worker
 * Manages batch scraping: creates hidden tabs, scrapes job pages, reports progress
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
  if (details.reason === 'install') {
    console.log('[Job Scraper] Extension installed!');
  } else if (details.reason === 'update') {
    console.log('[Job Scraper] Extension updated');
  }
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
    // Start the batch asynchronously
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
  const validUrls = urls.filter(u => u && u.url && !u.url.startsWith('chrome://'));

  batchState.urls = validUrls;
  batchState.results = [];
  batchState.currentIndex = 0;
  batchState.totalCount = validUrls.length;
  batchState.isRunning = true;
  batchState.isCancelled = false;
  batchState.errors = [];

  // Notify popup that batch started
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
      company: jobLink.company,
      role: jobLink.role,
    });

    console.log(`[Batch] [${i + 1}/${validUrls.length}] Processing: ${jobLink.url.substring(0, 80)}...`);

    try {
      const tab = await createTab(jobLink.url);
      if (!tab || !tab.id) {
        batchState.errors.push({ url: jobLink.url, error: 'Failed to create tab' });
        continue;
      }

      // Wait for tab to fully load
      const loaded = await waitForTabLoad(tab.id);
      if (!loaded) {
        batchState.errors.push({ url: jobLink.url, error: 'Tab load timeout' });
        safeCloseTab(tab.id);
        continue;
      }

      // Extra wait for dynamic content (JS-rendered pages like LinkedIn/Naukri)
      await delay(2500);

      // Send scrape message to the tab's content script
      const result = await sendMessageToTab(tab.id, {
        action: 'scrape',
        options: { dedup: true, deepMode: true },
      });

      if (result && result.data && result.data.length > 0) {
        // Add company/role from listing card if extraction failed on detail page
        const enriched = result.data.map(item => ({
          ...item,
          company: (item.company && !item.company.startsWith('[COMPANY_')) ? item.company : (jobLink.company || item.company),
          role: (item.role && !item.role.startsWith('[ROLE_')) ? item.role : (jobLink.role || item.role),
          skills: item.skills || [],
          highlights: item.highlights || '',
          location: item.location || '',
          experience: item.experience || '',
          education: item.education || '',
          employmentType: item.employmentType || '',
          department: item.department || '',
          industry: item.industry || '',
        }));
        batchState.results.push(...enriched);
        console.log(`[Batch] [${i + 1}/${validUrls.length}] Got ${enriched.length} entry(ies)`);
      } else {
        // If scraping failed, create entry from what we have from the listing card
        if (jobLink.company) {
          batchState.results.push({
            company: jobLink.company,
            role: jobLink.role || '[ROLE_NOT_FOUND]',
            description: '',
            descriptionBullets: [],
            source: 'batch-listing-card',
          });
          console.log(`[Batch] [${i + 1}/${validUrls.length}] Using listing card data for: ${jobLink.company}`);
        } else {
          batchState.errors.push({ url: jobLink.url, error: 'No data extracted' });
          console.log(`[Batch] [${i + 1}/${validUrls.length}] No data extracted`);
        }
      }

      // Close the tab
      safeCloseTab(tab.id);
    } catch (err) {
      console.error(`[Batch] Error processing ${jobLink.url}:`, err);
      batchState.errors.push({ url: jobLink.url, error: err.message });
    }

    // Rate limiting: wait between requests
    if (i < validUrls.length - 1 && !batchState.isCancelled) {
      await delay(1500);
    }
  }

  batchState.isRunning = false;
  console.log(`[Batch] Complete: ${batchState.results.length} entries from ${batchState.currentIndex} of ${validUrls.length} URLs`);

  // Notify popup that batch is done
  notifyPopup('batch-complete', {
    totalUrls: validUrls.length,
    processedUrls: batchState.currentIndex,
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
    const timeout = 15000; // 15 second timeout
    let resolved = false;

    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        resolve(false); // timeout
      }
    }, timeout);

    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === 'complete' && !resolved) {
        resolved = true;
        clearTimeout(timer);
        // Wait a small additional time for content script initialization
        setTimeout(() => resolve(true), 500);
      }
    }

    chrome.tabs.onUpdated.addListener(listener);

    // Also resolve if tab doesn't exist or errors
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(false);
      }
    }, timeout + 1000);
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
