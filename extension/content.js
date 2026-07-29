/**
 * Job Scraper Pro - Content Script
 * Runs on any page and extracts company/job data from the live DOM.
 * Uses the real browser session - no anti-bot issues!
 */

// Company detection patterns
const COMPANY_SUFFIXES = [
  'inc', 'ltd', 'limited', 'pvt', 'private', 'corp', 'corporation',
  'llc', 'llp', 'plc', 'gmbh', 'ag', 'sa', 'bv', 'nv', 'pty',
  'technologies', 'tech', 'solutions', 'services', 'consulting',
  'group', 'holdings', 'enterprises', 'systems', 'software',
  'digital', 'global', 'international', 'industries', 'labs',
  'ventures', 'partners', 'associates', 'analytics', 'data', 'infotech',
];

// Common non-company words to exclude
const EXCLUDE_WORDS = new Set([
  'home', 'about', 'contact', 'search', 'login', 'sign', 'register',
  'jobs', 'careers', 'apply', 'submit', 'next', 'previous', 'page',
  'loading', 'error', 'menu', 'navigation', 'footer', 'header',
  'skip', 'share', 'save', 'cancel', 'delete', 'edit', 'filter',
  'sort', 'view', 'list', 'grid', 'back', 'more', 'less', 'all',
  'submit', 'reset', 'send', 'close', 'open', 'help', 'faq', 'features',
  'products', 'services', 'solutions', 'pricing', 'blog', 'contact us',
]);

// ─── Listen for scrape requests from popup ─────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'scrape') {
    try {
      const result = scrapePage(request.options || {});
      sendResponse(result);
    } catch (err) {
      sendResponse({ error: err.message, data: [] });
    }
  }
  return true; // Keep channel open for async response
});

// ─── Main scrape function ──────────────────────────────────────────────────

function scrapePage(options = {}) {
  const { dedup = true, deepMode = true, cssSelectors = {} } = options;
  const seenFingerprints = new Set();
  const items = [];

  console.log('[Job Scraper] Starting page analysis...');
  console.log('[Job Scraper] URL:', window.location.href);

  // Strategy 1: JSON-LD structured data (most reliable)
  if (deepMode) {
    const jsonldItems = extractJSONLD();
    for (const item of jsonldItems) {
      if (isValid(item, dedup, seenFingerprints)) {
        items.push(item);
      }
    }
    console.log(`[Job Scraper] JSON-LD found ${jsonldItems.length} items`);
  }

  // Strategy 2: CSS Selectors (user-provided or auto-detected)
  const selectorItems = extractViaSelectors(cssSelectors, dedup, seenFingerprints);
  for (const item of selectorItems) {
    if (isValid(item, dedup, seenFingerprints)) {
      items.push(item);
    }
  }
  console.log(`[Job Scraper] Selectors found ${selectorItems.length} items`);

  // Strategy 3: Tables (only if no data found yet or deep mode)
  if (deepMode || items.length === 0) {
    const tableItems = extractFromTables(dedup, seenFingerprints);
    for (const item of tableItems) {
      if (isValid(item, dedup, seenFingerprints)) {
        items.push(item);
      }
    }
    console.log(`[Job Scraper] Tables found ${tableItems.length} items`);
  }

  // Strategy 4: Card/list patterns
  if (deepMode || items.length === 0) {
    const cardItems = extractFromCards(cssSelectors, dedup, seenFingerprints);
    for (const item of cardItems) {
      if (isValid(item, dedup, seenFingerprints)) {
        items.push(item);
      }
    }
    console.log(`[Job Scraper] Cards found ${cardItems.length} items`);
  }

  // Strategy 5: Text patterns (fallback)
  if (items.length === 0) {
    const textItems = extractFromTextPatterns(dedup, seenFingerprints);
    for (const item of textItems) {
      if (isValid(item, dedup, seenFingerprints)) {
        items.push(item);
      }
    }
    console.log(`[Job Scraper] Text patterns found ${textItems.length} items`);
  }

  console.log(`[Job Scraper] Total: ${items.length} entries found`);
  return { data: items, count: items.length };
}

// ─── Validation ────────────────────────────────────────────────────────────

function isValid(item, dedup, seenFingerprints) {
  if (!item || !item.company || item.company.trim().length < 2) return false;
  if (EXCLUDE_WORDS.has(item.company.toLowerCase().trim())) return false;

  if (dedup) {
    const fp = (item.description || item.company).toLowerCase().trim().substring(0, 80);
    if (seenFingerprints.has(fp)) return false;
    seenFingerprints.add(fp);
  }
  return true;
}

function looksLikeCompany(text) {
  if (!text || text.length < 2) return false;
  const t = text.trim();
  const tl = t.toLowerCase();

  // Check suffix
  if (COMPANY_SUFFIXES.some(s => tl.includes(s))) return true;

  // Check for 2+ capitalized words
  const caps = (t.match(/[A-Z][a-z]+/g) || []).length;
  if (caps >= 2) return true;

  // Single capitalized word of reasonable length
  if (caps === 1 && t.length >= 4 && t.length <= 40) {
    return !EXCLUDE_WORDS.has(tl);
  }

  // All-caps words (like "TCS", "IBM", "HCL")
  if (/^[A-Z]{2,5}$/.test(t)) return true;

  return false;
}

// ─── Strategy 1: JSON-LD ──────────────────────────────────────────────────

function extractJSONLD() {
  const items = [];
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');

  for (const script of scripts) {
    try {
      let data = JSON.parse(script.textContent);
      if (!Array.isArray(data)) data = [data];

      for (const item of data) {
        const type = item['@type'] || '';
        let company = '';
        let role = '';
        let desc = '';

        if (type && type.includes('JobPosting')) {
          const org = item.hiringOrganization || {};
          company = typeof org === 'string' ? org : (org.name || '');
          role = item.title || '';
          desc = item.description || item.responsibilities || '';
        } else if (['Organization', 'Corporation', 'Company', 'LocalBusiness'].includes(type)) {
          company = item.name || '';
          role = 'Company';
        } else if (type === 'ItemList' || type === 'ListItem') {
          const list = item.itemListElement || [];
          for (const li of list) {
            const liData = li.item || li;
            if (liData.name) {
              items.push({ company: liData.name, role: 'Listed Company', description: '', descriptionBullets: [] });
            }
          }
          continue;
        }

        if (company && role) {
          items.push({
            company,
            role,
            description: desc || '',
            descriptionBullets: desc ? extractBullets(desc) : [],
          });
        }
      }
    } catch (e) { /* skip invalid JSON */ }
  }
  return items;
}

// ─── Strategy 2: CSS Selectors ────────────────────────────────────────────

function extractViaSelectors(cssSelectors, dedup, seen) {
  const items = [];

  // If user provided custom selectors, use them on the whole page
  if (cssSelectors.company && cssSelectors.role) {
    const companyEls = document.querySelectorAll(cssSelectors.company);
    const roleEls = cssSelectors.role ? document.querySelectorAll(cssSelectors.role) : [];
    const descEls = cssSelectors.description ? document.querySelectorAll(cssSelectors.description) : [];

    const count = Math.max(companyEls.length, roleEls.length);
    for (let i = 0; i < count; i++) {
      const company = companyEls[i] ? companyEls[i].textContent.trim() : '';
      const role = roleEls[i] ? roleEls[i].textContent.trim() : '';
      const desc = descEls[i] ? descEls[i].textContent.trim() : '';
      if (company) {
        items.push({ company, role: role || 'Listed Entry', description: desc, descriptionBullets: desc ? extractBullets(desc) : [] });
      }
    }
    return items;
  }

  // Auto-detect common company patterns
  // Look for tables/listings by common class names
  const commonSelectors = [
    'a[href*="/company/"]', 'a[href*="/companies/"]',
    '[class*="company-name"]', '[class*="companyName"]',
    '[class*="org-name"]', '[class*="orgName"]',
    'h3[class*="title"]', 'h4[class*="title"]',
    'a[data-company]', '[data-company-name]',
    '.employer', '.employer-name',
  ];

  for (const sel of commonSelectors) {
    const els = document.querySelectorAll(sel);
    if (els.length > 2) {
      for (const el of els) {
        const text = el.textContent.trim();
        if (text && looksLikeCompany(text)) {
          // Try to find a nearby job title
          const parent = el.closest('li, div, article, tr') || el.parentElement;
          const nearbyTitle = findJobTitleNearby(parent, el);
          items.push({
            company: text,
            role: nearbyTitle || 'Listed Entry',
            description: '',
            descriptionBullets: [],
          });
        }
      }
      if (items.length > 0) break;
    }
  }

  return items;
}

function findJobTitleNearby(parent, excludeEl) {
  if (!parent) return '';
  // Look for common job title elements
  const selectors = [
    'h2', 'h3', 'h4', 'a[class*="title"]', 'a[class*="job"]',
    '[class*="job-title"]', '[class*="jobTitle"]', '[class*="position"]',
    '[class*="role"]', '[class*="designation"]',
  ];
  for (const sel of selectors) {
    const el = parent.querySelector(sel);
    if (el && el !== excludeEl) {
      const text = el.textContent.trim();
      if (text && text.length > 1 && text.length < 200 && !looksLikeCompany(text)) {
        return text;
      }
    }
  }
  // Try all links
  const links = parent.querySelectorAll('a');
  for (const link of links) {
    if (link !== excludeEl) {
      const text = link.textContent.trim();
      if (text && text.length > 2 && text.length < 150 && !looksLikeCompany(text)) {
        return text;
      }
    }
  }
  return '';
}

// ─── Strategy 3: Tables ───────────────────────────────────────────────────

function extractFromTables(dedup, seen) {
  const items = [];
  const tables = document.querySelectorAll('table');
  if (tables.length === 0) return items;

  for (const table of tables) {
    const rows = table.querySelectorAll('tr');
    if (rows.length < 2) continue;

    // Detect columns from headers
    const headerCells = rows[0].querySelectorAll('th, td');
    const headers = Array.from(headerCells).map(th => th.textContent.trim().toLowerCase());

    let companyIdx = -1, roleIdx = -1, descIdx = -1;
    headers.forEach((h, i) => {
      if (/company|organization|firm|employer|name/.test(h)) companyIdx = i;
      if (/job|title|position|role|designation/.test(h)) roleIdx = i;
      if (/description|details|info|about/.test(h)) descIdx = i;
    });

    // Auto-detect company column from first data row
    if (companyIdx === -1 && rows.length > 1) {
      const cells = rows[1].querySelectorAll('td');
      cells.forEach((cell, i) => {
        const text = cell.textContent.trim();
        if (looksLikeCompany(text)) companyIdx = i;
      });
    }

    // Extract data
    for (let r = 1; r < rows.length; r++) {
      const cells = rows[r].querySelectorAll('td');
      if (cells.length === 0) continue;

      let company = '', role = '', desc = '';
      if (companyIdx >= 0 && companyIdx < cells.length) {
        company = cells[companyIdx].textContent.trim();
      } else if (cells.length > 0) {
        const first = cells[0].textContent.trim();
        if (looksLikeCompany(first)) company = first;
      }
      if (roleIdx >= 0 && roleIdx < cells.length) role = cells[roleIdx].textContent.trim();
      if (descIdx >= 0 && descIdx < cells.length) desc = cells[descIdx].textContent.trim();

      if (company) {
        items.push({ company, role: role || 'Listed Entry', description: desc, descriptionBullets: desc ? extractBullets(desc) : [] });
      }
    }
  }
  return items;
}

// ─── Strategy 4: Cards/Listings ────────────────────────────────────────────

function extractFromCards(cssSelectors, dedup, seen) {
  const items = [];

  const cardSelectors = [
    'article', 'div[class*="card"]', 'div[class*="list-item"]',
    'div[class*="result"]', 'li[class*="list"]', 'div[class*="company"]',
    'div[class*="job"]', 'div[class*="tuple"]', 'div[class*="row"]',
    'div[class*="listing"]', 'section[class*="card"]',
    'div[data-company]', 'div[data-job]', 'li[class*="job"]',
  ];

  let cards = [];
  for (const sel of cardSelectors) {
    const found = document.querySelectorAll(sel);
    if (found.length > 1 && found.length < 200) {
      cards = found;
      break;
    }
  }

  if (cards.length === 0) return items;

  for (const card of cards) {
    try {
      let company = '', role = '', desc = '';

      // Custom selectors within each card
      if (cssSelectors.company) {
        const el = card.querySelector(cssSelectors.company);
        if (el) company = el.textContent.trim();
      }
      if (cssSelectors.role) {
        const el = card.querySelector(cssSelectors.role);
        if (el) role = el.textContent.trim();
      }
      if (cssSelectors.description) {
        const el = card.querySelector(cssSelectors.description);
        if (el) desc = el.textContent.trim();
      }

      if (company && role) {
        items.push({ company, role, description: desc, descriptionBullets: desc ? extractBullets(desc) : [] });
        continue;
      }

      // Auto-detect: find company-like text and role-like text
      const allLinks = card.querySelectorAll('a, strong, h2, h3, h4');
      const texts = Array.from(allLinks)
        .map(el => el.textContent.trim())
        .filter(t => t.length > 1);

      for (const t of texts) {
        if (!company && looksLikeCompany(t)) company = t;
        else if (!role && !looksLikeCompany(t) && t.length < 200) role = t;
      }

      if (!company) {
        // Try first link/text as company
        const firstLink = card.querySelector('a');
        if (firstLink) {
          const t = firstLink.textContent.trim();
          if (t.length > 1) company = t;
        }
      }

      // Look for description
      const descEl = card.querySelector('p, div[class*="desc"], div[class*="summary"]');
      if (descEl) desc = descEl.textContent.trim();

      if (company) {
        items.push({ company, role: role || 'Listed Entry', description: desc, descriptionBullets: desc ? extractBullets(desc) : [] });
      }
    } catch (e) { /* skip card */ }
  }
  return items;
}

// ─── Strategy 5: Text Patterns ─────────────────────────────────────────────

function extractFromTextPatterns(dedup, seen) {
  const items = [];
  // Limit to first 50KB for performance on large pages
  const bodyText = document.body.innerText.substring(0, 50000);

  // Find company names with known suffixes
  const pattern = new RegExp(
    `([A-Z][A-Za-z0-9\\s&.-]{1,40}?)(${COMPANY_SUFFIXES.join('|')})`,
    'gi'
  );

  let match;
  const foundCompanies = new Set();
  while ((match = pattern.exec(bodyText)) !== null) {
    const company = match[0].trim();
    if (company.length > 2 && !EXCLUDE_WORDS.has(company.toLowerCase())) {
      // Try to find a job title near this match
      const context = bodyText.substring(
        Math.max(0, match.index - 100),
        Math.min(bodyText.length, match.index + 200)
      );
      const titleMatch = context.match(/(?:hiring|looking for|seeking|position|role|job)[:\s]+([A-Z][A-Za-z\s/]+?)(?:\n|\.|,)/i);
      const role = titleMatch ? titleMatch[1].trim() : '';

      if (!foundCompanies.has(company)) {
        foundCompanies.add(company);
        items.push({ company, role: role || 'Listed Entry', description: '', descriptionBullets: [] });
      }
    }
  }
  return items;
}

// ─── Bullet point extraction ───────────────────────────────────────────────

function extractBullets(text) {
  if (!text) return [];
  const lines = text.split(/[•·●◆◇▪▸▹►▻‣⁃⦿✦✧\-]\s*|\n+|(?:\d+[.)])\s*/);
  return lines
    .map(l => l.trim())
    .filter(l => l.length > 10)
    .slice(0, 50);
}
