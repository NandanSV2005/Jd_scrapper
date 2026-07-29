/**
 * Job Scraper Pro - Background Service Worker
 * Handles extension lifecycle and messaging
 */

// Handle extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[Job Scraper] Extension installed!');
    // Open onboarding/getting started page (optional)
  } else if (details.reason === 'update') {
    console.log('[Job Scraper] Extension updated to v1.0.0');
  }
});

// Handle keyboard shortcut (if any)
chrome.commands?.onCommand?.addListener((command) => {
  if (command === 'scrape-page') {
    // Send scrape command to active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'scrape', options: { dedup: true } })
          .catch(() => {});
      }
    });
  }
});

// Handle messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getPageInfo') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        sendResponse({
          url: tabs[0].url,
          title: tabs[0].title,
        });
      }
    });
    return true; // Keep channel open
  }
});
